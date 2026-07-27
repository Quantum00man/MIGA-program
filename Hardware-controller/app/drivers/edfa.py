import socket
import time
from typing import Iterable


class EdfaCommunicationError(RuntimeError):
    pass


def probe_device(ip: str, port: int, timeout_sec: float) -> None:
    with socket.create_connection((ip, port), timeout=timeout_sec):
        return


def send_commands(
    ip: str,
    port: int,
    timeout_sec: float,
    command_delay_sec: float,
    commands: Iterable[str],
) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout_sec)
            sock.connect((ip, port))
            for command in commands:
                sock.sendall((command + "\r\n").encode("ascii", errors="ignore"))
                time.sleep(command_delay_sec)
    except OSError as exc:
        raise EdfaCommunicationError(
            f"Failed to communicate with EDFA device at {ip}:{port}: {exc}"
        ) from exc
