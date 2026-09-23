"""Read-only access to a Thorlabs PM100A through the installed TLPMX driver."""

from __future__ import annotations

import ctypes
import math
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


DRIVER_PATH = Path(r"C:\Program Files\IVI Foundation\VISA\Win64\Bin\TLPMX_64.dll")
TARGET_SERIAL = "P1002033"


class PowerMeterError(RuntimeError):
    pass


class PM100AReader:
    def __init__(self, serial_number: str = TARGET_SERIAL):
        self.serial_number = serial_number
        self._lock = Lock()
        self._driver = None
        self._session = ctypes.c_uint32()

    def _load_driver(self):
        if self._driver is not None:
            return self._driver
        if not DRIVER_PATH.is_file():
            raise PowerMeterError(f"Thorlabs TLPMX driver is missing: {DRIVER_PATH}")
        dll = ctypes.WinDLL(str(DRIVER_PATH))
        for name, argtypes in {
            "TLPMX_findRsrc": [ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)],
            "TLPMX_getRsrcName": [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_char_p],
            "TLPMX_getRsrcInfo": [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint16)],
            "TLPMX_init": [ctypes.c_char_p, ctypes.c_uint16, ctypes.c_uint16, ctypes.POINTER(ctypes.c_uint32)],
            "TLPMX_close": [ctypes.c_uint32],
            "TLPMX_getWavelength": [ctypes.c_uint32, ctypes.c_int16, ctypes.POINTER(ctypes.c_double), ctypes.c_uint16],
            "TLPMX_writeRaw": [ctypes.c_uint32, ctypes.c_char_p],
            "TLPMX_readRaw": [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)],
            "TLPMX_errorMessage": [ctypes.c_uint32, ctypes.c_int32, ctypes.c_char_p],
        }.items():
            function = getattr(dll, name)
            function.argtypes = argtypes
            function.restype = ctypes.c_int32
        self._driver = dll
        return dll

    def _check(self, status: int):
        if status < 0:
            message = ctypes.create_string_buffer(512)
            self._driver.TLPMX_errorMessage(self._session.value, status, message)
            raise PowerMeterError(message.value.decode("utf-8", errors="replace") or f"TLPMX error {status}")

    def _connect(self):
        driver = self._load_driver()
        count = ctypes.c_uint32()
        self._check(driver.TLPMX_findRsrc(0, ctypes.byref(count)))
        for index in range(count.value):
            model = ctypes.create_string_buffer(256)
            serial = ctypes.create_string_buffer(256)
            maker = ctypes.create_string_buffer(256)
            available = ctypes.c_uint16()
            self._check(driver.TLPMX_getRsrcInfo(0, index, model, serial, maker, ctypes.byref(available)))
            if model.value.decode(errors="replace") != "PM100A" or serial.value.decode(errors="replace") != self.serial_number:
                continue
            if not available.value:
                raise PowerMeterError("PM100A is in use by another application.")
            resource = ctypes.create_string_buffer(256)
            self._check(driver.TLPMX_getRsrcName(0, index, resource))
            self._check(driver.TLPMX_init(resource.value, 0, 0, ctypes.byref(self._session)))
            return
        raise PowerMeterError(f"PM100A {self.serial_number} was not found by the Thorlabs driver.")

    def read(self) -> dict:
        with self._lock:
            if not self._session.value:
                self._connect()
            answer = ctypes.create_string_buffer(256)
            answer_size = ctypes.c_uint32()
            wavelength = ctypes.c_double()
            try:
                self._check(self._driver.TLPMX_writeRaw(self._session.value, b"MEAS:POW?"))
                self._check(self._driver.TLPMX_readRaw(self._session.value, answer, len(answer), ctypes.byref(answer_size)))
                power = float(answer.value.strip())
                self._check(self._driver.TLPMX_getWavelength(self._session.value, 0, ctypes.byref(wavelength), 0))
                if not math.isfinite(power):
                    raise PowerMeterError("PM100A returned a non-finite power reading.")
                return {
                    "power_w": power,
                    "wavelength_nm": wavelength.value,
                    "serial_number": self.serial_number,
                    "measured_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                }
            except Exception:
                self._close_unlocked()
                raise

    def _close_unlocked(self):
        if self._session.value:
            self._driver.TLPMX_close(self._session.value)
            self._session = ctypes.c_uint32()

    def close(self):
        with self._lock:
            self._close_unlocked()
