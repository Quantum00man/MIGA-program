"""Buffered, bounded LAN text transport. No automatic retry of writes."""

import socket
import time

from .models import ConnectionSettings


class InstrumentError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


class LanTransport:
    def __init__(self, settings: ConnectionSettings):
        self.settings = settings
        self.socket = None
        self.buffer = bytearray()

    def connect(self):
        try:
            self.socket = socket.create_connection(
                (str(self.settings.host), self.settings.port), self.settings.timeout_s
            )
            self.socket.settimeout(self.settings.timeout_s)
        except OSError as exc:
            self.close()
            raise InstrumentError("Cannot connect to the instrument. Check IP, port 9221 and network cabling.", 503) from exc

    def close(self):
        if self.socket:
            self.socket.close()
        self.socket = None
        self.buffer.clear()

    def write(self, command: str):
        if not self.socket:
            raise InstrumentError("Not connected. Connect before sending commands.", 409)
        try:
            self.socket.sendall((command + "\n").encode("ascii"))
        except OSError as exc:
            self.close()
            raise InstrumentError("Connection lost while sending a command. Instrument state is unknown; reconnect before continuing.", 503) from exc

    def query(self, command: str) -> str:
        self.write(command)
        deadline = time.monotonic() + self.settings.timeout_s
        try:
            while b"\n" not in self.buffer:
                remaining_s = deadline - time.monotonic()
                if remaining_s <= 0:
                    raise TimeoutError("Reply deadline exceeded")
                self.socket.settimeout(remaining_s)
                block = self.socket.recv(4096)
                if not block:
                    raise OSError("Peer disconnected")
                self.buffer.extend(block)
                if len(self.buffer) > 16384:
                    raise OSError("Reply exceeded text limit")
            line, _, remaining = self.buffer.partition(b"\n")
            self.buffer = bytearray(remaining)
            self.socket.settimeout(self.settings.timeout_s)
            return line.decode("ascii").strip()
        except (OSError, UnicodeError) as exc:
            self.close()
            raise InstrumentError("Instrument reply timed out or was invalid. State is unknown; reconnect and check the instrument.", 503) from exc
