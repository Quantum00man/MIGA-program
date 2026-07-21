from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DurationConvention(str, Enum):
    """Interpretation of the user-entered Gaussian pulse duration."""

    SIGMA = "Gaussian sigma"
    AMPLITUDE_FWHM = "Gaussian amplitude FWHM"
    INTENSITY_FWHM = "Gaussian intensity FWHM"


@dataclass(frozen=True)
class PulseSpec:
    """Finite-duration Bragg pulse specification."""

    duration_us: float
    target_area_rad: float


@dataclass(frozen=True)
class InterferometerConfig:
    """Pulse-sequence and solver settings."""

    beamsplitter: PulseSpec
    mirror: PulseSpec
    dark_time_ms: float
    duration_convention: DurationConvention = DurationConvention.SIGMA
    truncate_sigma: float = 4.5
    time_steps: int = 320


@dataclass(frozen=True)
class EnsembleConfig:
    """Velocity-selection ensemble expressed in Doppler detuning units."""

    distribution_fwhm_khz: float
    nominal_center_khz: float = 0.0
    shot_noise_sigma_khz: float = 4.0


@dataclass(frozen=True)
class AnalysisConfig:
    """Sampling and sweep settings."""

    center_scan_halfwidth_khz: float = 12.0
    center_scan_points: int = 241
    noise_sweep_max_khz: float = 8.0
    noise_sweep_points: int = 31
    monte_carlo_shots: int = 256
    gauss_hermite_points: int = 41
    detuning_grid_points: int = 401
    random_seed: int = 12345
