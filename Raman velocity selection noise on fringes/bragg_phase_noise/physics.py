from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .config import DurationConvention, InterferometerConfig, PulseSpec


SQRT_2 = math.sqrt(2.0)
SQRT_2PI = math.sqrt(2.0 * math.pi)


def khz_to_hz(value_khz: float) -> float:
    return 1.0e3 * value_khz


def hz_to_khz(value_hz: float) -> float:
    return value_hz / 1.0e3


def fwhm_to_sigma(fwhm: float) -> float:
    return fwhm / (2.0 * math.sqrt(2.0 * math.log(2.0)))


def duration_to_sigma_s(duration_us: float, convention: DurationConvention) -> float:
    """Convert a user-entered Gaussian duration to the envelope RMS width."""

    duration_s = duration_us * 1.0e-6
    if convention is DurationConvention.SIGMA:
        return duration_s
    if convention is DurationConvention.AMPLITUDE_FWHM:
        return duration_s / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    if convention is DurationConvention.INTENSITY_FWHM:
        return duration_s / (2.0 * math.sqrt(math.log(2.0)))
    raise ValueError(f"Unsupported duration convention: {convention}")


def calibrate_peak_rabi(pulse: PulseSpec, config: InterferometerConfig) -> float:
    """Return the peak Rabi frequency in rad/s for a truncated Gaussian pulse."""

    sigma_s = duration_to_sigma_s(pulse.duration_us, config.duration_convention)
    truncation = math.erf(config.truncate_sigma / math.sqrt(2.0))
    area = sigma_s * SQRT_2PI * truncation
    return pulse.target_area_rad / area


def gaussian_envelope(times_s: np.ndarray, sigma_s: float, peak_rabi_rad_s: float) -> np.ndarray:
    return peak_rabi_rad_s * np.exp(-0.5 * np.square(times_s / sigma_s))


def step_propagator(detuning_rad_s: float, rabi_rad_s: float, dt_s: float) -> np.ndarray:
    """Exact two-level propagator for one piecewise-constant time step."""

    if abs(detuning_rad_s) < 1.0e-18 and abs(rabi_rad_s) < 1.0e-18:
        return np.eye(2, dtype=complex)

    generator = np.array(
        [
            [-detuning_rad_s, rabi_rad_s],
            [rabi_rad_s, detuning_rad_s],
        ],
        dtype=complex,
    )
    norm = math.hypot(detuning_rad_s, rabi_rad_s)
    half_angle = 0.5 * norm * dt_s
    return (
        math.cos(half_angle) * np.eye(2, dtype=complex)
        - 1j * math.sin(half_angle) / norm * generator
    )


@dataclass
class PulseInterpolator:
    """Interpolate precomputed pulse unitaries over detuning."""

    detuning_grid_hz: np.ndarray
    unitary_table: np.ndarray

    def evaluate(self, detuning_hz: np.ndarray | float) -> np.ndarray:
        detuning = np.atleast_1d(np.asarray(detuning_hz, dtype=float))
        values = np.empty(detuning.shape + (2, 2), dtype=complex)
        for row in range(2):
            for col in range(2):
                real = np.interp(
                    detuning,
                    self.detuning_grid_hz,
                    self.unitary_table[:, row, col].real,
                )
                imag = np.interp(
                    detuning,
                    self.detuning_grid_hz,
                    self.unitary_table[:, row, col].imag,
                )
                values[..., row, col] = real + 1j * imag

        if np.isscalar(detuning_hz):
            return values[0]
        return values


def build_pulse_interpolator(
    pulse: PulseSpec,
    config: InterferometerConfig,
    detuning_grid_hz: np.ndarray,
) -> PulseInterpolator:
    sigma_s = duration_to_sigma_s(pulse.duration_us, config.duration_convention)
    peak_rabi_rad_s = calibrate_peak_rabi(pulse, config)
    time_limit_s = config.truncate_sigma * sigma_s
    dt_s = 2.0 * time_limit_s / config.time_steps
    times_s = np.linspace(
        -time_limit_s + 0.5 * dt_s,
        time_limit_s - 0.5 * dt_s,
        config.time_steps,
    )
    rabi_envelope = gaussian_envelope(times_s, sigma_s, peak_rabi_rad_s)

    table = np.empty((detuning_grid_hz.size, 2, 2), dtype=complex)
    for index, detuning_hz in enumerate(detuning_grid_hz):
        detuning_rad_s = 2.0 * math.pi * detuning_hz
        propagator = np.eye(2, dtype=complex)
        for rabi_rad_s in rabi_envelope:
            propagator = step_propagator(detuning_rad_s, float(rabi_rad_s), dt_s) @ propagator
        table[index] = propagator

    return PulseInterpolator(detuning_grid_hz=detuning_grid_hz, unitary_table=table)
