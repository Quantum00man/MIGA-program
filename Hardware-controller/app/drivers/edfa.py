import socket
import time
from typing import Iterable


class EdfaCommunicationError(RuntimeError):
    pass


def _strip_telnet_negotiation(data: bytes, sock: socket.socket) -> bytes:
    """Refuse optional Telnet modes and return only shell application data."""
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
            sock.sendall(bytes((IAC, reply, option)))
            index += 3
        elif command == SB:
            end = data.find(bytes((IAC, SE)), index + 2)
            index = len(data) if end < 0 else end + 2
        else:
            index += 2
    return bytes(output)


def _read_until_prompt(sock: socket.socket, timeout_sec: float) -> str:
    deadline = time.monotonic() + timeout_sec
    received = bytearray()
    while time.monotonic() < deadline:
        sock.settimeout(max(0.1, min(0.5, deadline - time.monotonic())))
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            continue
        if not chunk:
            raise EdfaCommunicationError("Telnet connection closed before the shell prompt was received.")
        cleaned = _strip_telnet_negotiation(chunk, sock)
        if cleaned:
            received.extend(cleaned)
            text = received.decode("ascii", errors="replace")
            if text.rstrip().endswith("#"):
                return text
    text = received.decode("ascii", errors="replace")
    raise EdfaCommunicationError(
        f"Timed out waiting for the EDFA shell prompt. Last response: {text[-200:]!r}"
    )


def _open_telnet_shell(ip: str, port: int, timeout_sec: float) -> socket.socket:
    sock = socket.create_connection((ip, port), timeout=timeout_sec)
    try:
        sock.settimeout(min(timeout_sec, 0.5))
        try:
            initial = sock.recv(2048)
        except socket.timeout:
            initial = b""
        if initial:
            _strip_telnet_negotiation(initial, sock)
        sock.sendall(b"\r\n")
        _read_until_prompt(sock, timeout_sec)
        return sock
    except Exception:
        sock.close()
        raise


def probe_device(ip: str, port: int, timeout_sec: float) -> None:
    try:
        with _open_telnet_shell(ip, port, timeout_sec):
            return
    except (OSError, EdfaCommunicationError) as exc:
        raise EdfaCommunicationError(
            f"Failed to open the EDFA Telnet shell at {ip}:{port}: {exc}"
        ) from exc


def send_commands(
    ip: str,
    port: int,
    timeout_sec: float,
    command_delay_sec: float,
    commands: Iterable[str],
) -> None:
    try:
        with _open_telnet_shell(ip, port, timeout_sec) as sock:
            for command in commands:
                sock.sendall((command + "\r\n").encode("ascii", errors="ignore"))
                response = _read_until_prompt(sock, max(timeout_sec, command_delay_sec + 1.0))
                if "/bin/sh:" in response or "command not found" in response.lower():
                    raise EdfaCommunicationError(
                        f"EDFA shell rejected command {command!r}: {response[-300:]}"
                    )
                if command_delay_sec:
                    time.sleep(command_delay_sec)
    except (OSError, EdfaCommunicationError) as exc:
        raise EdfaCommunicationError(
            f"Failed to communicate with EDFA device at {ip}:{port}: {exc}"
        ) from exc
