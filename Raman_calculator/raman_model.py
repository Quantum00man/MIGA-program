from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


TRAPEZOID = getattr(np, "trapezoid", np.trapz)

PI = math.pi
BOLTZMANN_CONSTANT_J_K = 1.380649e-23
RB87_MASS_KG = 1.443160e-25
RAMAN_WAVELENGTH_M = 780e-9
RECOIL_VELOCITY_M_S = 5.88e-3
SATURATION_INTENSITY_W_M2 = 16.7
FINE_STRUCTURE_SPLITTING_MHZ = 157.0
NATURAL_LINEWIDTH_MHZ = 6.065
EFFECTIVE_WAVENUMBER_M_INV = 4.0 * PI / RAMAN_WAVELENGTH_M

RAMAN_TRANSITION = "Raman"
BRAGG_TRANSITION = "Bragg"
TRANSITION_KINDS = {RAMAN_TRANSITION, BRAGG_TRANSITION}

DEFAULT_P1_MW = 14.0
DEFAULT_P2_MW = DEFAULT_P1_MW / 2.6
DEFAULT_DESACC_MHZ = -1000.0
DEFAULT_W0_MM = 11.5
DEFAULT_TAU_MIN_US = 0.0
DEFAULT_TAU_MAX_US = 300.0
DEFAULT_TAU_POINTS = 400
DEFAULT_INITIAL_CLOUD_SIGMA_MM = 5.0
DEFAULT_EXPANSION_TIME_MS = 56.0
DEFAULT_TWO_PHOTON_DETUNING_KHZ = 0.0
DEFAULT_ATTENUATION = 1.0
DEFAULT_GAIN = 1.0
DEFAULT_RADIAL_POINTS = 220
DEFAULT_VELOCITY_POINTS = 220
DEFAULT_RADIAL_CUTOFF_WAISTS = 2.0
DEFAULT_VELOCITY_CUTOFF_SIGMA = 3.0

DEFAULT_TRANSVERSE_SIGMA_M_S = 2.65 * RECOIL_VELOCITY_M_S
DEFAULT_TEMPERATURE_UK = (
    RB87_MASS_KG * DEFAULT_TRANSVERSE_SIGMA_M_S**2 / BOLTZMANN_CONSTANT_J_K * 1e6
)


@dataclass(slots=True)
class RamanSimulationParameters:
    transition_kind: str = RAMAN_TRANSITION
    transverse_temperature_uK: float = DEFAULT_TEMPERATURE_UK
    use_separate_longitudinal_temperature: bool = False
    longitudinal_temperature_uK: float = DEFAULT_TEMPERATURE_UK
    desacc_mhz: float = DEFAULT_DESACC_MHZ
    p1_mw: float = DEFAULT_P1_MW
    p2_mw: float = DEFAULT_P2_MW
    w0_mm: float = DEFAULT_W0_MM
    tau_min_us: float = DEFAULT_TAU_MIN_US
    tau_max_us: float = DEFAULT_TAU_MAX_US
    tau_points: int = DEFAULT_TAU_POINTS
    expansion_time_ms: float = DEFAULT_EXPANSION_TIME_MS
    initial_cloud_sigma_mm: float = DEFAULT_INITIAL_CLOUD_SIGMA_MM
    two_photon_detuning_khz: float = DEFAULT_TWO_PHOTON_DETUNING_KHZ
    attenuation: float = DEFAULT_ATTENUATION
    gain: float = DEFAULT_GAIN
    radial_points: int = DEFAULT_RADIAL_POINTS
    velocity_points: int = DEFAULT_VELOCITY_POINTS
    radial_cutoff_waists: float = DEFAULT_RADIAL_CUTOFF_WAISTS
    velocity_cutoff_sigma: float = DEFAULT_VELOCITY_CUTOFF_SIGMA

    @property
    def transverse_temperature_k(self) -> float:
        return self.transverse_temperature_uK * 1e-6

    @property
    def longitudinal_temperature_k(self) -> float:
        if self.use_separate_longitudinal_temperature:
            return self.longitudinal_temperature_uK * 1e-6
        return self.transverse_temperature_k

    @property
    def p1_w(self) -> float:
        return self.p1_mw * 1e-3

    @property
    def p2_w(self) -> float:
        return self.p2_mw * 1e-3

    @property
    def w0_m(self) -> float:
        return self.w0_mm * 1e-3

    @property
    def initial_cloud_sigma_m(self) -> float:
        return self.initial_cloud_sigma_mm * 1e-3

    @property
    def expansion_time_s(self) -> float:
        return self.expansion_time_ms * 1e-3

    @property
    def desacc_rad_s(self) -> float:
        return 2.0 * PI * self.desacc_mhz * 1e6

    @property
    def delta2_rad_s(self) -> float:
        return 2.0 * PI * FINE_STRUCTURE_SPLITTING_MHZ * 1e6

    @property
    def gamma_rad_s(self) -> float:
        return 2.0 * PI * NATURAL_LINEWIDTH_MHZ * 1e6

    @property
    def two_photon_detuning_rad_s(self) -> float:
        return 2.0 * PI * self.two_photon_detuning_khz * 1e3

    @property
    def transverse_velocity_sigma_m_s(self) -> float:
        return math.sqrt(
            BOLTZMANN_CONSTANT_J_K * self.transverse_temperature_k / RB87_MASS_KG
        )

    @property
    def longitudinal_velocity_sigma_m_s(self) -> float:
        return math.sqrt(
            BOLTZMANN_CONSTANT_J_K * self.longitudinal_temperature_k / RB87_MASS_KG
        )

    def tau_values_us(self) -> np.ndarray:
        return np.linspace(self.tau_min_us, self.tau_max_us, self.tau_points)

    def cloud_time_values_s(self) -> np.ndarray:
        return np.linspace(0.0, self.expansion_time_s, self.tau_points)

    def cloud_radius_sigma_m(self, time_s: np.ndarray | float) -> np.ndarray | float:
        return np.sqrt(
            self.initial_cloud_sigma_m**2
            + (np.asarray(time_s) * self.transverse_velocity_sigma_m_s) ** 2
        )

    def validate(self) -> None:
        if self.transition_kind not in TRANSITION_KINDS:
            raise ValueError("Transition kind must be Raman or Bragg.")
        if self.transverse_temperature_uK <= 0.0:
            raise ValueError("Transverse atomic temperature must be positive.")
        if self.longitudinal_temperature_uK <= 0.0:
            raise ValueError("Longitudinal atomic temperature must be positive.")
        if self.w0_mm <= 0.0:
            raise ValueError("Beam waist w0 must be positive.")
        if self.p1_mw < 0.0 or self.p2_mw < 0.0:
            raise ValueError("Beam powers must be non-negative.")
        if self.tau_min_us < 0.0:
            raise ValueError("tau_min must be non-negative.")
        if self.tau_max_us <= self.tau_min_us:
            raise ValueError("tau_max must be larger than tau_min.")
        if self.tau_points < 4:
            raise ValueError("At least four tau points are required.")
        if self.expansion_time_ms < 0.0:
            raise ValueError("Expansion time must be non-negative.")
        if self.initial_cloud_sigma_mm <= 0.0:
            raise ValueError("Initial cloud size must be positive.")
        if self.attenuation <= 0.0:
            raise ValueError("Attenuation must be positive.")
        if self.gain <= 0.0:
            raise ValueError("Gain must be positive.")
        if self.radial_points < 10 or self.velocity_points < 10:
            raise ValueError("Integration grids must have at least ten points.")
        if self.radial_cutoff_waists <= 0.0 or self.velocity_cutoff_sigma <= 0.0:
            raise ValueError("Integration cutoffs must be positive.")
        if abs(self.desacc_mhz) < 1e-9:
            raise ValueError("Large detuning must not be zero.")
        if abs(self.desacc_mhz + FINE_STRUCTURE_SPLITTING_MHZ) < 1e-9:
            raise ValueError(
                "Large detuning must not coincide with the desacc + delta2 singularity."
            )


@dataclass(slots=True)
class RamanSimulationResult:
    tau_us: np.ndarray
    transition_probability: np.ndarray
    cloud_time_s: np.ndarray
    cloud_time_display: np.ndarray
    cloud_time_unit: str
    cloud_radius_mm: np.ndarray
    on_axis_rabi_khz: float
    pi_pulse_time_us: float
    ensemble_optimal_pulse_time_us: float
    ensemble_optimal_probability: float
    longitudinal_sigma_mm_s: float
    transverse_sigma_mm_s: float
    expansion_cloud_sigma_mm: float
    p1_peak_intensity_w_m2: float
    p2_peak_intensity_w_m2: float


def gaussian_intensity(power_w: float, radius_m: np.ndarray, waist_m: float) -> np.ndarray:
    return 2.0 * power_w / (PI * waist_m**2) * np.exp(-2.0 * radius_m**2 / waist_m**2)


def effective_raman_rabi_frequency(
    radius_m: np.ndarray, params: RamanSimulationParameters
) -> np.ndarray:
    intensity_1 = gaussian_intensity(params.p1_w, radius_m, params.w0_m)
    intensity_2 = gaussian_intensity(params.p2_w, radius_m, params.w0_m)
    coupling_term = (
        5.0 / (24.0 * params.desacc_rad_s)
        + 3.0 / (24.0 * (params.desacc_rad_s + params.delta2_rad_s))
    ) / 2.0
    omega = (
        params.gamma_rad_s**2
        / params.attenuation
        * params.gain
        * np.sqrt(intensity_1 * intensity_2)
        / (2.0 * SATURATION_INTENSITY_W_M2)
        * coupling_term
    )
    return np.abs(omega)


def effective_bragg_rabi_frequency(
    radius_m: np.ndarray, params: RamanSimulationParameters
) -> np.ndarray:
    """Effective Bragg coupling translated from the supplied Mathematica model."""
    intensity_1 = gaussian_intensity(params.p1_w, radius_m, params.w0_m)
    intensity_2 = gaussian_intensity(params.p2_w, radius_m, params.w0_m)
    coupling_term = (
        5.0 / (24.0 * params.desacc_rad_s)
        + 3.0 / (24.0 * (params.desacc_rad_s + params.delta2_rad_s))
    ) / 2.0
    omega = (
        params.gamma_rad_s**2
        / params.attenuation
        * params.gain
        * np.sqrt(intensity_1 * intensity_2)
        / (2.0 * SATURATION_INTENSITY_W_M2)
        * coupling_term
    )
    return np.abs(omega)


def effective_rabi_frequency(
    radius_m: np.ndarray, params: RamanSimulationParameters
) -> np.ndarray:
    if params.transition_kind == BRAGG_TRANSITION:
        return effective_bragg_rabi_frequency(radius_m, params)
    return effective_raman_rabi_frequency(radius_m, params)


def longitudinal_velocity_pdf(velocity_m_s: np.ndarray, sigma_m_s: float) -> np.ndarray:
    return np.exp(-0.5 * (velocity_m_s / sigma_m_s) ** 2) / (
        math.sqrt(2.0 * PI) * sigma_m_s
    )


def radial_density(radius_m: np.ndarray, sigma_m: float) -> np.ndarray:
    variance = sigma_m**2
    return np.exp(-(radius_m**2) / (2.0 * variance)) / (2.0 * PI * variance)


def choose_display_time_axis(time_s: np.ndarray) -> tuple[np.ndarray, str]:
    maximum_time_s = float(np.max(time_s)) if time_s.size else 0.0
    if maximum_time_s >= 1.0:
        return time_s, "s"
    if maximum_time_s >= 1e-3:
        return time_s * 1e3, "ms"
    if maximum_time_s >= 1e-6:
        return time_s * 1e6, "us"
    return time_s * 1e9, "ns"


def first_peak_with_quadratic_refinement(
    x: np.ndarray, y: np.ndarray
) -> tuple[float, float]:
    """Return the first interior local maximum, refined with a parabola.

    If the scan contains no interior maximum, return NaN values rather than
    labeling a scan boundary as an ensemble-optimal pi pulse.
    """
    if x.size < 3 or y.size != x.size:
        return math.nan, math.nan

    peak_indices = np.flatnonzero(
        (y[1:-1] > y[:-2]) & (y[1:-1] >= y[2:])
    )
    if peak_indices.size == 0:
        return math.nan, math.nan

    index = int(peak_indices[0] + 1)
    x_triplet = x[index - 1 : index + 2]
    y_triplet = y[index - 1 : index + 2]
    coefficients = np.polyfit(x_triplet, y_triplet, 2)
    curvature, slope, offset = coefficients
    if curvature >= 0.0 or not np.all(np.isfinite(coefficients)):
        return float(x[index]), float(y[index])

    refined_x = float(-slope / (2.0 * curvature))
    if refined_x < float(x_triplet[0]) or refined_x > float(x_triplet[-1]):
        return float(x[index]), float(y[index])
    refined_y = float(curvature * refined_x**2 + slope * refined_x + offset)
    return refined_x, float(np.clip(refined_y, 0.0, 1.0))


def simulate_rabi_oscillation(
    params: RamanSimulationParameters, chunk_size: int = 64
) -> RamanSimulationResult:
    params.validate()

    tau_us = params.tau_values_us()
    tau_s = tau_us * 1e-6
    cloud_time_s = params.cloud_time_values_s()
    cloud_time_display, cloud_time_unit = choose_display_time_axis(cloud_time_s)
    cloud_radius_mm = params.cloud_radius_sigma_m(cloud_time_s) * 1e3

    radius_grid = np.linspace(
        0.0, params.radial_cutoff_waists * params.w0_m, params.radial_points
    )
    velocity_grid = np.linspace(
        -params.velocity_cutoff_sigma * params.longitudinal_velocity_sigma_m_s,
        params.velocity_cutoff_sigma * params.longitudinal_velocity_sigma_m_s,
        params.velocity_points,
    )

    expansion_cloud_sigma_m = float(params.cloud_radius_sigma_m(params.expansion_time_s))
    radial_pdf = radial_density(radius_grid, expansion_cloud_sigma_m)
    velocity_pdf = longitudinal_velocity_pdf(
        velocity_grid, params.longitudinal_velocity_sigma_m_s
    )

    omega_r = effective_rabi_frequency(radius_grid[:, None], params)
    detuning = (
        velocity_grid[None, :] * EFFECTIVE_WAVENUMBER_M_INV
        - params.two_photon_detuning_rad_s
    )
    generalized_rabi = np.sqrt(omega_r**2 + detuning**2)

    prefactor = (
        2.0
        * PI
        * radius_grid[:, None]
        * radial_pdf[:, None]
        * velocity_pdf[None, :]
        * (omega_r / generalized_rabi) ** 2
    )

    transition_probability = np.empty_like(tau_s)
    for start in range(0, tau_s.size, chunk_size):
        stop = min(start + chunk_size, tau_s.size)
        tau_chunk = tau_s[start:stop]
        sin_term = np.sin(generalized_rabi[..., None] * tau_chunk / 2.0) ** 2
        chunk_integrand = prefactor[..., None] * sin_term
        velocity_integrated = TRAPEZOID(chunk_integrand, velocity_grid, axis=1)
        transition_probability[start:stop] = TRAPEZOID(
            velocity_integrated, radius_grid, axis=0
        )

    transition_probability = np.clip(transition_probability, 0.0, 1.0)
    ensemble_optimal_time_us, ensemble_optimal_probability = (
        first_peak_with_quadratic_refinement(tau_us, transition_probability)
    )

    omega_zero = float(effective_rabi_frequency(np.array([0.0]), params)[0])
    if omega_zero > 0.0:
        pi_pulse_time_us = PI / omega_zero * 1e6
    else:
        pi_pulse_time_us = math.inf

    return RamanSimulationResult(
        tau_us=tau_us,
        transition_probability=transition_probability,
        cloud_time_s=cloud_time_s,
        cloud_time_display=cloud_time_display,
        cloud_time_unit=cloud_time_unit,
        cloud_radius_mm=cloud_radius_mm,
        on_axis_rabi_khz=omega_zero / (2.0 * PI * 1e3),
        pi_pulse_time_us=pi_pulse_time_us,
        ensemble_optimal_pulse_time_us=ensemble_optimal_time_us,
        ensemble_optimal_probability=ensemble_optimal_probability,
        longitudinal_sigma_mm_s=params.longitudinal_velocity_sigma_m_s * 1e3,
        transverse_sigma_mm_s=params.transverse_velocity_sigma_m_s * 1e3,
        expansion_cloud_sigma_mm=expansion_cloud_sigma_m * 1e3,
        p1_peak_intensity_w_m2=float(gaussian_intensity(params.p1_w, 0.0, params.w0_m)),
        p2_peak_intensity_w_m2=float(gaussian_intensity(params.p2_w, 0.0, params.w0_m)),
    )
