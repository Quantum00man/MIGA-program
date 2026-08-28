from __future__ import annotations

import math
import threading
import time

import serial
from serial.tools import list_ports


BAUDRATE = 19200
MAX_OUTPUT_DBM = 33.0


class BraggEdfaCommunicationError(RuntimeError):
    pass


def parse_answer(answer: str) -> str:
    text = answer.strip().replace("\r", "").replace("\n", "")
    if not text:
        raise BraggEdfaCommunicationError("No response from the Bragg EDFA.")
    if text.endswith("/"):
        raise BraggEdfaCommunicationError("Command is not supported by this firmware.")
    if text in {"*", "#", "$"}:
        messages = {"*": "Unknown command.", "#": "Command not authorized.", "$": "Invalid command."}
        raise BraggEdfaCommunicationError(messages[text])
    if "=" in text:
        return text.split("=", 1)[1].strip()
    if text.endswith("!"):
        return "OK"
    return text


def input_power_values(raw: str) -> dict:
    microwatts = float(raw)
    dbm = None if microwatts <= 0 else 10 * math.log10(microwatts / 1000)
    return {"raw": raw, "microwatts": microwatts, "dbm": dbm}


def output_power_values(raw: str) -> dict:
    milliwatts = float(raw)
    dbm = None if milliwatts <= 0 else 10 * math.log10(milliwatts)
    return {"raw": raw, "milliwatts": milliwatts, "dbm": dbm}


def available_ports() -> list[dict]:
    return [
        {"device": port.device, "description": port.description or "Serial port"}
        for port in list_ports.comports()
    ]


class BraggEdfaClient:
    def __init__(self, port_name: str, timeout_sec: float = 0.8):
        self.port_name = port_name
        self.timeout_sec = timeout_sec
        self.port: serial.Serial | None = None
        self.lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return bool(self.port and self.port.is_open)

    def connect(self) -> str:
        self.close()
        try:
            self.port = serial.Serial(
                self.port_name,
                BAUDRATE,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=self.timeout_sec,
                write_timeout=self.timeout_sec,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
            self.port.reset_input_buffer()
            return parse_answer(self.command("SNU?"))
        except Exception as exc:
            self.close()
            if isinstance(exc, BraggEdfaCommunicationError):
                raise
            raise BraggEdfaCommunicationError(
                f"Failed to connect to Bragg EDFA on {self.port_name}: {exc}"
            ) from exc

    def close(self) -> None:
        if self.port and self.port.is_open:
            self.port.close()
        self.port = None

    def command(self, command: str, write_allowed: bool = False) -> str:
        command = command.strip().upper()
        if "=" in command and not write_allowed:
            raise BraggEdfaCommunicationError("Write command blocked.")
        if not self.connected:
            raise BraggEdfaCommunicationError("Bragg EDFA is not connected.")
        try:
            with self.lock:
                assert self.port is not None
                self.port.reset_input_buffer()
                self.port.write((command + "\r").encode("ascii"))
                self.port.flush()
                deadline = time.monotonic() + max(1.2, self.timeout_sec)
                data = bytearray()
                while time.monotonic() < deadline:
                    chunk = self.port.read(self.port.in_waiting or 1)
                    if chunk:
                        data.extend(chunk)
                        if b"\r" in data or data[-1:] in b"!*/#$":
                            break
                return parse_answer(data.decode("ascii", errors="replace"))
        except Exception as exc:
            if isinstance(exc, BraggEdfaCommunicationError):
                raise
            raise BraggEdfaCommunicationError(f"Serial command {command!r} failed: {exc}") from exc

    def read_state(self) -> dict:
        input_raw = self.command("PUE?")
        output_raw = self.command("PUS?")
        state_raw = self.command("ASS?")
        return {
            "input_power": input_power_values(input_raw),
            "output_power": output_power_values(output_raw),
            "output_mode": state_raw,
            "output_state": {"0": "OFF", "1": "ON · ACC", "2": "ON · APC"}.get(
                state_raw, f"MODE {state_raw}"
            ),
        }

    def set_apc_setpoint(self, value_dbm: float) -> None:
        if not 0 <= value_dbm <= MAX_OUTPUT_DBM:
            raise ValueError(f"Output power must be between 0 and {MAX_OUTPUT_DBM:g} dBm.")
        response = self.command(f"CPU={round(value_dbm * 10)}", write_allowed=True)
        if response != "OK":
            raise BraggEdfaCommunicationError(f"Unexpected setpoint response: {response}")

    def set_output(self, turn_on: bool) -> None:
        response = self.command("ASS=2" if turn_on else "ASS=0", write_allowed=True)
        if response != "OK":
            raise BraggEdfaCommunicationError(f"Unexpected output response: {response}")
