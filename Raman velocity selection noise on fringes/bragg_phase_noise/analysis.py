from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .config import AnalysisConfig, EnsembleConfig, InterferometerConfig
from .physics import build_pulse_interpolator, fwhm_to_sigma, hz_to_khz, khz_to_hz


def wrapped_phase_difference(phase_a: np.ndarray, phase_b: np.ndarray) -> np.ndarray:
    return np.angle(np.exp(1j * (phase_a - phase_b)))


def local_phase_std(phases: np.ndarray, reference_phase: float) -> float:
    deltas = wrapped_phase_difference(phases, reference_phase)
    if deltas.size <= 1:
        return 0.0
    return float(np.std(deltas, ddof=1))


def unwrap_series(phases: np.ndarray) -> np.ndarray:
    return np.unwrap(np.asarray(phases, dtype=float))


@dataclass(frozen=True)
class ModelOutputs:
    center_scan_khz: np.ndarray
    total_phase_scan_rad: np.ndarray
    diffraction_phase_scan_rad: np.ndarray
    total_contrast_scan: np.ndarray
    diffraction_contrast_scan: np.ndarray
    noise_sweep_khz: np.ndarray
    total_sigma_phi_linear_rad: np.ndarray
    total_sigma_phi_monte_carlo_rad: np.ndarray
    diffraction_sigma_phi_linear_rad: np.ndarray
    diffraction_sigma_phi_monte_carlo_rad: np.ndarray
    nominal_total_phase_rad: float
    nominal_diffraction_phase_rad: float
    nominal_total_contrast: float
    nominal_diffraction_contrast: float
    total_phase_slope_rad_per_khz: float
    diffraction_phase_slope_rad_per_khz: float


class BraggPhaseNoiseModel:
    """Ensemble-averaged two-level Bragg interferometer phase-noise model."""

    def __init__(
        self,
        interferometer: InterferometerConfig,
        ensemble: EnsembleConfig,
        analysis: AnalysisConfig,
    ) -> None:
        self.interferometer = interferometer
        self.ensemble = ensemble
        self.analysis = analysis
        self.dark_time_s = interferometer.dark_time_ms * 1.0e-3
        self.distribution_sigma_hz = khz_to_hz(fwhm_to_sigma(ensemble.distribution_fwhm_khz))
        self.nominal_center_hz = khz_to_hz(ensemble.nominal_center_khz)
        self.reference_noise_sigma_hz = khz_to_hz(ensemble.shot_noise_sigma_khz)
        self.gh_nodes, self.gh_weights = np.polynomial.hermite.hermgauss(
            analysis.gauss_hermite_points
        )

        detuning_span_hz = khz_to_hz(
            max(
                abs(ensemble.nominal_center_khz) + analysis.center_scan_halfwidth_khz + 6.0 * ensemble.distribution_fwhm_khz,
                abs(ensemble.nominal_center_khz) + 7.0 * analysis.noise_sweep_max_khz + 6.0 * ensemble.distribution_fwhm_khz,
                abs(ensemble.nominal_center_khz) + 25.0,
            )
        )
        self.detuning_grid_hz = np.linspace(
            -detuning_span_hz,
            detuning_span_hz,
            analysis.detuning_grid_points,
        )

        self.beamsplitter_pulse = build_pulse_interpolator(
            pulse=interferometer.beamsplitter,
            config=interferometer,
            detuning_grid_hz=self.detuning_grid_hz,
        )
        self.mirror_pulse = build_pulse_interpolator(
            pulse=interferometer.mirror,
            config=interferometer,
            detuning_grid_hz=self.detuning_grid_hz,
        )

    def _fringe_coefficients_for_detuning(
        self,
        detuning_hz: np.ndarray,
        include_free_evolution: bool,
    ) -> tuple[np.ndarray, np.ndarray]:
        detuning = np.asarray(detuning_hz, dtype=float)
        flat = detuning.reshape(-1)

        beamsplitter = self.beamsplitter_pulse.evaluate(flat)
        mirror = self.mirror_pulse.evaluate(flat)

        state_after_first = beamsplitter[:, :, 0].copy()
        if include_free_evolution:
            phase = np.exp(1j * math.pi * flat * self.dark_time_s)
        else:
            phase = np.ones_like(flat, dtype=complex)

        state_after_first[:, 0] *= phase
        state_after_first[:, 1] *= np.conjugate(phase)
        state_after_mirror = np.einsum("nij,nj->ni", mirror, state_after_first)
        state_before_final = state_after_mirror.copy()
        state_before_final[:, 0] *= phase
        state_before_final[:, 1] *= np.conjugate(phase)

        alpha = beamsplitter[:, 0, 0] * state_before_final[:, 0]
        beta = beamsplitter[:, 0, 1] * state_before_final[:, 1]
        fringe_coefficient = alpha * np.conjugate(beta)
        offset = np.abs(alpha) ** 2 + np.abs(beta) ** 2

        return fringe_coefficient.reshape(detuning.shape), offset.reshape(detuning.shape)

    def _ensemble_average(
        self,
        center_hz: np.ndarray,
        include_free_evolution: bool,
    ) -> tuple[np.ndarray, np.ndarray]:
        centers = np.atleast_1d(np.asarray(center_hz, dtype=float))
        detuning_samples = centers[:, None] + math.sqrt(2.0) * self.distribution_sigma_hz * self.gh_nodes[None, :]
        coefficients, offsets = self._fringe_coefficients_for_detuning(
            detuning_hz=detuning_samples,
            include_free_evolution=include_free_evolution,
        )
        weights = self.gh_weights / math.sqrt(math.pi)
        avg_coefficients = coefficients @ weights
        avg_offsets = offsets @ weights
        return avg_coefficients, avg_offsets

    @staticmethod
    def _phase_from_coefficients(coefficients: np.ndarray) -> np.ndarray:
        return -np.angle(coefficients)

    @staticmethod
    def _contrast_from_coefficients(coefficients: np.ndarray, offsets: np.ndarray) -> np.ndarray:
        contrast = np.zeros_like(offsets, dtype=float)
        valid = offsets > 1.0e-14
        contrast[valid] = 2.0 * np.abs(coefficients[valid]) / offsets[valid]
        return contrast

    def evaluate_centers(
        self,
        center_khz: np.ndarray | float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        centers_hz = khz_to_hz(np.asarray(center_khz, dtype=float))
        full_coefficients, full_offsets = self._ensemble_average(
            center_hz=centers_hz,
            include_free_evolution=True,
        )
        diffraction_coefficients, diffraction_offsets = self._ensemble_average(
            center_hz=centers_hz,
            include_free_evolution=False,
        )

        total_phase = self._phase_from_coefficients(full_coefficients)
        diffraction_phase = self._phase_from_coefficients(diffraction_coefficients)
        total_contrast = self._contrast_from_coefficients(full_coefficients, full_offsets)
        diffraction_contrast = self._contrast_from_coefficients(
            diffraction_coefficients,
            diffraction_offsets,
        )
        return total_phase, diffraction_phase, total_contrast, diffraction_contrast

    def _phase_slope_rad_per_khz(self, nominal_center_khz: float, include_free_evolution: bool) -> float:
        step_hz = max(10.0, self.distribution_sigma_hz / 200.0)
        step_khz = hz_to_khz(step_hz)
        center = nominal_center_khz
        if include_free_evolution:
            phase_plus = self.evaluate_centers(center + step_khz)[0][0]
            phase_minus = self.evaluate_centers(center - step_khz)[0][0]
        else:
            phase_plus = self.evaluate_centers(center + step_khz)[1][0]
            phase_minus = self.evaluate_centers(center - step_khz)[1][0]

        phase_delta = wrapped_phase_difference(phase_plus, phase_minus)
        return float(phase_delta / (2.0 * step_khz))

    def _monte_carlo_phase_noise(
        self,
        noise_sigma_khz: float,
        reference_phase_rad: float,
        include_free_evolution: bool,
    ) -> float:
        if noise_sigma_khz <= 0.0:
            return 0.0

        rng_seed = self.analysis.random_seed + (0 if include_free_evolution else 1_000_000)
        rng = np.random.default_rng(rng_seed)
        centers_khz = rng.normal(
            loc=self.ensemble.nominal_center_khz,
            scale=noise_sigma_khz,
            size=self.analysis.monte_carlo_shots,
        )

        if include_free_evolution:
            phases = self.evaluate_centers(centers_khz)[0]
        else:
            phases = self.evaluate_centers(centers_khz)[1]
        return local_phase_std(phases, reference_phase_rad)

    def run(self) -> ModelOutputs:
        center_scan_khz = np.linspace(
            self.ensemble.nominal_center_khz - self.analysis.center_scan_halfwidth_khz,
            self.ensemble.nominal_center_khz + self.analysis.center_scan_halfwidth_khz,
            self.analysis.center_scan_points,
        )
        total_phase_scan, diffraction_phase_scan, total_contrast_scan, diffraction_contrast_scan = (
            self.evaluate_centers(center_scan_khz)
        )

        nominal_outputs = self.evaluate_centers(self.ensemble.nominal_center_khz)
        nominal_total_phase = float(nominal_outputs[0][0])
        nominal_diffraction_phase = float(nominal_outputs[1][0])
        nominal_total_contrast = float(nominal_outputs[2][0])
        nominal_diffraction_contrast = float(nominal_outputs[3][0])

        total_phase_slope = self._phase_slope_rad_per_khz(
            nominal_center_khz=self.ensemble.nominal_center_khz,
            include_free_evolution=True,
        )
        diffraction_phase_slope = self._phase_slope_rad_per_khz(
            nominal_center_khz=self.ensemble.nominal_center_khz,
            include_free_evolution=False,
        )

        noise_sweep_khz = np.linspace(
            0.0,
            self.analysis.noise_sweep_max_khz,
            self.analysis.noise_sweep_points,
        )
        total_sigma_phi_linear = np.abs(total_phase_slope) * noise_sweep_khz
        diffraction_sigma_phi_linear = np.abs(diffraction_phase_slope) * noise_sweep_khz
        total_sigma_phi_monte_carlo = np.array(
            [
                self._monte_carlo_phase_noise(
                    noise_sigma_khz=value,
                    reference_phase_rad=nominal_total_phase,
                    include_free_evolution=True,
                )
                for value in noise_sweep_khz
            ]
        )
        diffraction_sigma_phi_monte_carlo = np.array(
            [
                self._monte_carlo_phase_noise(
                    noise_sigma_khz=value,
                    reference_phase_rad=nominal_diffraction_phase,
                    include_free_evolution=False,
                )
                for value in noise_sweep_khz
            ]
        )

        return ModelOutputs(
            center_scan_khz=center_scan_khz,
            total_phase_scan_rad=total_phase_scan,
            diffraction_phase_scan_rad=diffraction_phase_scan,
            total_contrast_scan=total_contrast_scan,
            diffraction_contrast_scan=diffraction_contrast_scan,
            noise_sweep_khz=noise_sweep_khz,
            total_sigma_phi_linear_rad=total_sigma_phi_linear,
            total_sigma_phi_monte_carlo_rad=total_sigma_phi_monte_carlo,
            diffraction_sigma_phi_linear_rad=diffraction_sigma_phi_linear,
            diffraction_sigma_phi_monte_carlo_rad=diffraction_sigma_phi_monte_carlo,
            nominal_total_phase_rad=nominal_total_phase,
            nominal_diffraction_phase_rad=nominal_diffraction_phase,
            nominal_total_contrast=nominal_total_contrast,
            nominal_diffraction_contrast=nominal_diffraction_contrast,
            total_phase_slope_rad_per_khz=total_phase_slope,
            diffraction_phase_slope_rad_per_khz=diffraction_phase_slope,
        )
