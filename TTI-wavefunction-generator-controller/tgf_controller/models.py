"""Public API models and physical constraints (TGF3000 manual, sections 3 and 23)."""

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, model_validator

MAX_FREQUENCY = 160_000_000.0


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ConnectionSettings(Model):
    mode: Literal["demo", "lan"] = "demo"
    host: IPvAnyAddress = "192.168.1.100"
    port: int = Field(default=9221, ge=1, le=65535)
    timeout_s: float = Field(default=3, ge=0.2, le=10)


class Modulation(Model):
    mode: Literal["off", "am", "fm"] = "off"
    frequency_hz: float = Field(default=1000, ge=0.000001, le=10_000_000)
    depth_percent: float = Field(default=50, ge=0, le=100)
    deviation_hz: float = Field(default=2000, ge=0, le=80_000_000)


def amplitude_vpp(value: float, unit: str) -> float:
    if unit == "Vrms":
        return value * 2 * math.sqrt(2)
    if unit == "dBm":
        return 2 * math.sqrt(2 * 50 * 0.001 * 10 ** (value / 10))
    return value


def amplitude_limit(frequency_hz: float) -> float:
    return 10.0 if frequency_hz <= 50e6 else 5.0 if frequency_hz <= 100e6 else 2.5


def quantize(value: float, step: str) -> float:
    return float(Decimal(str(value)).quantize(Decimal(step), rounding=ROUND_HALF_UP))


class ChannelSettings(Model):
    frequency_hz: float = Field(default=10000, ge=0.000001, le=MAX_FREQUENCY)
    amplitude: float = Field(default=1, ge=-120, le=100)
    amplitude_unit: Literal["Vpp", "Vrms", "dBm"] = "Vpp"
    phase_deg: float = Field(default=0, ge=-360, le=360)
    modulation: Modulation = Field(default_factory=Modulation)

    @model_validator(mode="after")
    def physical_limits(self):
        vpp = amplitude_vpp(self.amplitude, self.amplitude_unit)
        mod = self.modulation
        high = self.frequency_hz
        if mod.mode == "am" and high > 50e6:
            raise ValueError("AM requires a carrier frequency at or below 50 MHz.")
        if mod.mode == "fm":
            maximum = min(self.frequency_hz, MAX_FREQUENCY - self.frequency_hz, 80e6)
            if mod.deviation_hz > maximum:
                raise ValueError(f"FM deviation must be at most {maximum:g} Hz for this carrier.")
            high += mod.deviation_hz
        limit = amplitude_limit(high)
        if not (0.01 - 1e-12 <= vpp <= limit + 1e-12):
            raise ValueError(f"Amplitude must equal 0.01 to {limit:g} Vpp into 50 ohms at this frequency range.")
        return self

    def normalized(self) -> dict:
        """Commanded values. Not hardware readback; instrument may round further."""
        data = self.model_dump()
        data["frequency_hz"] = quantize(self.frequency_hz, "0.000001")
        data["phase_deg"] = quantize(self.phase_deg, "0.001")
        data["modulation"]["frequency_hz"] = quantize(self.modulation.frequency_hz, "0.000001")
        data["modulation"]["depth_percent"] = quantize(self.modulation.depth_percent, "0.01")
        data["modulation"]["deviation_hz"] = quantize(self.modulation.deviation_hz, "0.000001")
        data["amplitude_vpp"] = amplitude_vpp(self.amplitude, self.amplitude_unit)
        data["load_ohm"] = 50
        data["offset_v"] = 0
        return data


class OutputRequest(Model):
    enabled: bool = Field(strict=True)
