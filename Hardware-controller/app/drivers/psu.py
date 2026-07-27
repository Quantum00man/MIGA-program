import socket
import time


class PsuCommunicationError(RuntimeError):
    pass


class PsuClient:
    def __init__(self, ip: str, port: int, timeout_sec: float = 3.0):
        self.ip = ip.strip()
        self.port = int(port)
        self.timeout_sec = float(timeout_sec)
        self.sock: socket.socket | None = None

    def connect(self, timeout_sec: float | None = None, force: bool = False):
        timeout_sec = timeout_sec or self.timeout_sec
        if force:
            self.close()
        if self.sock is not None:
            self.sock.settimeout(timeout_sec)
            return

        sock = socket.create_connection((self.ip, self.port), timeout=timeout_sec)
        sock.settimeout(timeout_sec)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.sock = sock

    def close(self):
        sock, self.sock = self.sock, None
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    def _read_reply(self) -> str:
        if self.sock is None:
            raise PsuCommunicationError("Socket is not connected.")

        data = b""
        while b"\r\n" not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise PsuCommunicationError("Socket closed before a reply was received.")
            data += chunk
        return data.decode("ascii", errors="ignore").strip()

    def send_once(self, command: str, expect_reply: bool = False, timeout_sec: float | None = None):
        timeout_sec = timeout_sec or self.timeout_sec
        last_error: Exception | None = None

        for attempt in range(2):
            try:
                self.connect(timeout_sec=timeout_sec, force=attempt > 0)
                if self.sock is None:
                    raise PsuCommunicationError("Socket was not created.")

                self.sock.sendall((command + "\n").encode("ascii", errors="ignore"))
                if expect_reply:
                    return self._read_reply()
                return None
            except (OSError, PsuCommunicationError) as exc:
                last_error = exc
                self.close()
                time.sleep(0.2)

        raise PsuCommunicationError(
            f"Communication failed for command {command!r}: {last_error}"
        ) from last_error

    def output_on(self, channel: int):
        self.send_once(f"OP{channel} 1", expect_reply=False)

    def output_off(self, channel: int):
        self.send_once(f"OP{channel} 0", expect_reply=False)

    def output_state(self, channel: int) -> str:
        return self.send_once(f"OP{channel}?", expect_reply=True) or ""

    def idn(self) -> str:
        return self.send_once("*IDN?", expect_reply=True) or ""

    def set_independent_mode(self):
        self.send_once("OPALL 0", expect_reply=False)
        self.send_once("CONFIG 2", expect_reply=False)

    def config_get(self) -> str:
        return self.send_once("CONFIG?", expect_reply=True) or ""
