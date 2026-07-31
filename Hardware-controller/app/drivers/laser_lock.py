import re
import socket
import threading
from collections import deque
from datetime import datetime
from typing import Callable


LASER_CHANNELS = {
    "master": {
        "label": "Master",
        "command": "miga2 autolock_lock",
    },
    "slave_2d": {
        "label": "2D Slave",
        "command": "miga2 autolock_slave_2D",
    },
    "slave_3d": {
        "label": "3D Slave",
        "command": "miga2 autolock_slave_3D",
    },
    "repump": {
        "label": "Repump (RepR1)",
        "command": "miga2 autolock_slave_RepR1",
    },
}

_SCAN_PROGRESS_RE = re.compile(r"SCAN\s+\|.*?\|\s*(\d+)%\s+of\s+(\d+)\s+points")
_SCAN_RANGE_RE = re.compile(r"ctrlmin\s*=\s*(-?\d+),\s*ctrlmax\s*=\s*(-?\d+)")
_ZERO_CROSSING_RE = re.compile(r"ZC\s*@\s*(-?\d+)")
_LOCK_CTRL_RE = re.compile(r"lockctrl\s*=\s*(-?\d+)")
_LOCKING_RE = re.compile(
    r"locking at ctrltemp\s*=\s*(-?\d+).*?lockctrl\s*=\s*(-?\d+).*?pllerror\s*=\s*(-?[\d.]+)"
)
_TELEMETRY_RE = re.compile(
    r"pllerror\s*=\s*(-?[\d.]+)\s*V,\s*pidOut\s*=\s*(-?[\d.]+),\s*ctrltrmp\s*=\s*(-?\d+)"
)
_MASTER_SCAN_RE = re.compile(r"^scan\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)
_MASTER_PEAK_RE = re.compile(
    r"peak selected\s*:\s*ctrl\s*=\s*(-?\d+),\s*abspsignal\s*=\s*(-?[\d.]+)\s*V",
    re.IGNORECASE,
)
_MASTER_LOCK_RE = re.compile(
    r"lock at\s+(.+?),\s*absplock\s*=\s*(-?[\d.]+)",
    re.IGNORECASE,
)
_MASTER_OUTPUT_RE = re.compile(r"^\s*out0\s*=\s*(-?[\d.]+)", re.IGNORECASE)
_MASTER_ABSP_RE = re.compile(r"cnt\s*=\s*(\d+),\s*absp\s*=\s*(-?[\d.]+)\s*V", re.IGNORECASE)
_MASTER_DELOCK_RE = re.compile(
    r"delock detected\s*:\s*jumped from\s*(-?[\d.]+)\s*V\s*to\s*(-?[\d.]+)\s*V",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class LaserLockCommunicationError(RuntimeError):
    pass


class LaserLockSession:
    """One long-lived, foreground lock command over a dedicated Telnet socket."""

    def __init__(
        self,
        channel_key: str,
        on_update: Callable[[], None] | None = None,
        max_output_lines: int = 120,
    ):
        if channel_key not in LASER_CHANNELS:
            raise ValueError(f"Unknown laser lock channel: {channel_key}")
        self.channel_key = channel_key
        self.definition = LASER_CHANNELS[channel_key]
        self.on_update = on_update
        self._lock = threading.RLock()
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._output = deque(maxlen=max_output_lines)
        self._line_buffer = ""
        self._state = self._empty_state()

    def _empty_state(self) -> dict:
        return {
            "key": self.channel_key,
            "label": self.definition["label"],
            "command": self.definition["command"],
            "status": "IDLE",
            "connected": False,
            "scan_progress": None,
            "scan_points": None,
            "ctrlmin": None,
            "ctrlmax": None,
            "zero_crossings": [],
            "lockctrl": None,
            "ctrltemp": None,
            "pllerror": None,
            "pid_out": None,
            "scan_index": None,
            "scan_total": None,
            "selected_peak_ctrl": None,
            "absorption": None,
            "lock_absorption": None,
            "controller_output": None,
            "lock_check_count": None,
            "lock_verification_seen": False,
            "lock_time": "",
            "delock_from": None,
            "delock_to": None,
            "delock_count": 0,
            "last_update": "",
            "last_error": "",
            "recent_output": [],
        }

    def snapshot(self) -> dict:
        with self._lock:
            snapshot = dict(self._state)
            snapshot["zero_crossings"] = list(self._state["zero_crossings"])
            snapshot["recent_output"] = list(self._output)
            if snapshot["connected"] and snapshot["last_update"]:
                try:
                    age = (datetime.now().astimezone() - datetime.fromisoformat(snapshot["last_update"])).total_seconds()
                    if (
                        self.channel_key == "master"
                        and snapshot["lock_verification_seen"]
                        and snapshot["delock_count"] == 0
                        and snapshot["status"] not in ("ERROR", "DISCONNECTED", "STOPPED", "DELOCKED")
                        and age > 2
                    ):
                        snapshot["status"] = "LOCK_ACTIVE"
                    elif self.channel_key != "master" and age > 8 and snapshot["status"] in (
                        "SCANNING",
                        "ANALYZING",
                        "ACQUIRING",
                        "LOCK_ACTIVE",
                    ):
                        snapshot["status"] = "STALE"
                except ValueError:
                    pass
            return snapshot

    def start(self, ip: str, port: int, timeout_sec: float, relock: bool = False):
        if relock:
            self.stop(send_interrupt=True)
        elif self.is_running:
            raise LaserLockCommunicationError(
                f"{self.definition['label']} lock session is already running."
            )

        self._stop_event = threading.Event()
        with self._lock:
            self._output.clear()
            self._line_buffer = ""
            self._state = self._empty_state()
            self._state.update(
                {
                    "status": "CONNECTING",
                    "last_update": _now_iso(),
                }
            )

        self._thread = threading.Thread(
            target=self._run,
            args=(ip, port, timeout_sec),
            name=f"laser-lock-{self.channel_key}",
            daemon=True,
        )
        self._thread.start()
        self._notify()

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def stop(self, send_interrupt: bool = True):
        self._stop_event.set()
        sock = self._socket
        if sock:
            if send_interrupt:
                try:
                    sock.sendall(b"\x03")
                except OSError:
                    pass
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.5)
        with self._lock:
            self._socket = None
            self._state["connected"] = False
            if self._state["status"] not in ("ERROR", "DISCONNECTED"):
                self._state["status"] = "STOPPED"
            self._state["last_update"] = _now_iso()
        self._notify()

    def _run(self, ip: str, port: int, timeout_sec: float):
        try:
            sock = socket.create_connection((ip, port), timeout=timeout_sec)
            sock.settimeout(1.0)
            self._socket = sock
            with self._lock:
                self._state.update(
                    {
                        "status": "INITIALIZING",
                        "connected": True,
                        "last_update": _now_iso(),
                        "last_error": "",
                    }
                )
            self._notify()

            # The target exposes an already-configured root shell. A CR/LF first
            # obtains a clean prompt; the command itself is a fixed whitelist entry.
            sock.sendall(b"\r\n")
            self._drain_initial(sock)
            sock.sendall((self.definition["command"] + "\r\n").encode("ascii"))

            while not self._stop_event.is_set():
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    raise LaserLockCommunicationError("Telnet connection closed by the laser controller.")
                cleaned = self._strip_telnet_negotiation(chunk, sock)
                if cleaned:
                    self._consume_text(cleaned.decode("ascii", errors="replace"))
        except (OSError, LaserLockCommunicationError) as exc:
            if not self._stop_event.is_set():
                with self._lock:
                    self._state.update(
                        {
                            "status": "DISCONNECTED" if isinstance(exc, LaserLockCommunicationError) else "ERROR",
                            "connected": False,
                            "last_error": str(exc),
                            "last_update": _now_iso(),
                        }
                    )
                self._notify()
        finally:
            sock = self._socket
            self._socket = None
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass

    def _drain_initial(self, sock: socket.socket):
        original_timeout = sock.gettimeout()
        sock.settimeout(0.25)
        try:
            for _ in range(8):
                try:
                    chunk = sock.recv(2048)
                except socket.timeout:
                    break
                if not chunk:
                    break
                cleaned = self._strip_telnet_negotiation(chunk, sock)
                if cleaned:
                    self._consume_text(cleaned.decode("ascii", errors="replace"))
        finally:
            sock.settimeout(original_timeout)

    @staticmethod
    def _strip_telnet_negotiation(data: bytes, sock: socket.socket) -> bytes:
        # Minimal Telnet negotiation: refuse optional modes and retain application data.
        IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240
        output = bytearray()
        index = 0
        while index < len(data):
            byte = data[index]
            if byte != IAC:
                output.append(byte)
                index += 1
                continue
            if index + 1 >= len(data):
                break
            command = data[index + 1]
            if command == IAC:
                output.append(IAC)
                index += 2
            elif command in (WILL, WONT, DO, DONT) and index + 2 < len(data):
                option = data[index + 2]
                reply = DONT if command in (WILL, WONT) else WONT
                try:
                    sock.sendall(bytes((IAC, reply, option)))
                except OSError:
                    pass
                index += 3
            elif command == SB:
                end = data.find(bytes((IAC, SE)), index + 2)
                index = len(data) if end < 0 else end + 2
            else:
                index += 2
        return bytes(output)

    def _consume_text(self, text: str):
        normalized = text.replace("\r", "\n")
        with self._lock:
            self._line_buffer += normalized
            parts = self._line_buffer.split("\n")
            self._line_buffer = parts.pop()
        for line in parts:
            self._consume_line(line.strip())

    def _consume_line(self, line: str):
        if not line:
            return
        with self._lock:
            self._output.append(line)
            self._state["last_update"] = _now_iso()

            progress = _SCAN_PROGRESS_RE.search(line)
            if progress:
                self._state["status"] = "SCANNING"
                self._state["scan_progress"] = int(progress.group(1))
                self._state["scan_points"] = int(progress.group(2))

            scan_range = _SCAN_RANGE_RE.search(line)
            if scan_range:
                self._state["status"] = "ANALYZING"
                self._state["ctrlmin"] = int(scan_range.group(1))
                self._state["ctrlmax"] = int(scan_range.group(2))

            crossing = _ZERO_CROSSING_RE.search(line)
            if crossing:
                self._state["status"] = "ACQUIRING"
                self._state["zero_crossings"].append(int(crossing.group(1)))
                self._state["zero_crossings"] = self._state["zero_crossings"][-12:]

            lock_ctrl = _LOCK_CTRL_RE.search(line)
            if lock_ctrl:
                self._state["lockctrl"] = int(lock_ctrl.group(1))

            locking = _LOCKING_RE.search(line)
            if locking:
                self._state["status"] = "LOCK_ACTIVE"
                self._state["ctrltemp"] = int(locking.group(1))
                self._state["lockctrl"] = int(locking.group(2))
                self._state["pllerror"] = float(locking.group(3))

            telemetry = _TELEMETRY_RE.search(line)
            if telemetry:
                self._state["status"] = "LOCK_ACTIVE"
                self._state["pllerror"] = float(telemetry.group(1))
                self._state["pid_out"] = float(telemetry.group(2))
                self._state["ctrltemp"] = int(telemetry.group(3))

            if "-- locking --" in line:
                self._state["status"] = "LOCK_ACTIVE"

            if self.channel_key == "master":
                self._consume_master_line(line)
        self._notify()

    def _consume_master_line(self, line: str):
        scan = _MASTER_SCAN_RE.search(line)
        if scan:
            self._state["status"] = "SCANNING"
            self._state["scan_index"] = int(scan.group(1))
            self._state["scan_total"] = int(scan.group(2))
            self._state["delock_from"] = None
            self._state["delock_to"] = None

        peak = _MASTER_PEAK_RE.search(line)
        if peak:
            self._state["status"] = "ACQUIRING"
            self._state["selected_peak_ctrl"] = int(peak.group(1))
            self._state["absorption"] = float(peak.group(2))

        lock = _MASTER_LOCK_RE.search(line)
        if lock:
            self._state["status"] = "LOCK_ACTIVE"
            self._state["lock_time"] = lock.group(1).strip()
            self._state["lock_absorption"] = float(lock.group(2))
            self._state["absorption"] = float(lock.group(2))

        output = _MASTER_OUTPUT_RE.search(line)
        if output:
            self._state["controller_output"] = float(output.group(1))
            self._state["pid_out"] = float(output.group(1))

        absorption = _MASTER_ABSP_RE.search(line)
        if absorption:
            if self._state["status"] != "DELOCKED":
                self._state["status"] = "VERIFYING"
            self._state["lock_check_count"] = int(absorption.group(1))
            self._state["lock_verification_seen"] = True
            self._state["absorption"] = float(absorption.group(2))

        delock = _MASTER_DELOCK_RE.search(line)
        if delock:
            self._state["status"] = "DELOCKED"
            self._state["delock_from"] = float(delock.group(1))
            self._state["delock_to"] = float(delock.group(2))
            self._state["absorption"] = float(delock.group(2))
            self._state["delock_count"] += 1

    def _notify(self):
        if self.on_update:
            self.on_update()
