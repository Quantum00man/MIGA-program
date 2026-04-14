#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None


PI2 = 2.0 * math.pi
NEG_INF_DB = -300.0


@dataclass(frozen=True)
class LorentzianPeak:
    center_hz: float
    width_hz: float
    psd_db: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LorentzianPeak":
        if "psd_db" in data:
            psd_db = float(data["psd_db"])
        else:
            psd_db = legacy_asd_amplitude_to_psd_db(float(data["amplitude"]))
        return cls(
            center_hz=float(data["center_hz"]),
            width_hz=float(data["width_hz"]),
            psd_db=psd_db,
        )


@dataclass(frozen=True)
class NoiseModel:
    white_psd_db: float = NEG_INF_DB
    flicker_psd_1hz_db: float = NEG_INF_DB
    random_walk_psd_1hz_db: float = NEG_INF_DB
    peaks: tuple[LorentzianPeak, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NoiseModel":
        peaks = tuple(LorentzianPeak.from_dict(item) for item in data.get("peaks", []))
        return cls(
            white_psd_db=noise_term_db_from_dict(data, "white_psd_db", "white"),
            flicker_psd_1hz_db=noise_term_db_from_dict(data, "flicker_psd_1hz_db", "flicker"),
            random_walk_psd_1hz_db=noise_term_db_from_dict(data, "random_walk_psd_1hz_db", "random_walk"),
            peaks=peaks,
        )


@dataclass(frozen=True)
class PulseParameters:
    transfer_probability: float
    loss_probability: float = 0.0
    diffraction_phase_rad: float = 0.0
    transfer_jitter_std: float = 0.0
    phase_jitter_std_rad: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PulseParameters":
        return cls(
            transfer_probability=float(data["transfer_probability"]),
            loss_probability=float(data.get("loss_probability", 0.0)),
            diffraction_phase_rad=float(data.get("diffraction_phase_rad", 0.0)),
            transfer_jitter_std=float(data.get("transfer_jitter_std", 0.0)),
            phase_jitter_std_rad=float(data.get("phase_jitter_std_rad", 0.0)),
        )

    @classmethod
    def from_rabi_model(
        cls,
        omega_eff_rad_s: float,
        duration_s: float,
        detuning_rad_s: float = 0.0,
        *,
        loss_probability: float = 0.0,
        diffraction_phase_rad: float = 0.0,
        transfer_jitter_std: float = 0.0,
        phase_jitter_std_rad: float = 0.0,
    ) -> "PulseParameters":
        transfer_probability = coherent_transfer_probability(
            omega_eff_rad_s=omega_eff_rad_s,
            duration_s=duration_s,
            detuning_rad_s=detuning_rad_s,
        )
        return cls(
            transfer_probability=transfer_probability,
            loss_probability=loss_probability,
            diffraction_phase_rad=diffraction_phase_rad,
            transfer_jitter_std=transfer_jitter_std,
            phase_jitter_std_rad=phase_jitter_std_rad,
        )


@dataclass(frozen=True)
class InterferometerParameters:
    bragg_order: int = 4
    wavelength_m: float = 780e-9
    pulse_separation_s: float = 50e-3
    effective_acceleration_mps2: float = 0.0
    additional_phase_offset_rad: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InterferometerParameters":
        return cls(
            bragg_order=int(data.get("bragg_order", 4)),
            wavelength_m=float(data.get("wavelength_m", 780e-9)),
            pulse_separation_s=float(data.get("pulse_separation_s", 50e-3)),
            effective_acceleration_mps2=float(data.get("effective_acceleration_mps2", 0.0)),
            additional_phase_offset_rad=float(data.get("additional_phase_offset_rad", 0.0)),
        )


@dataclass(frozen=True)
class NoiseParameters:
    f_min_hz: float = 0.2
    f_max_hz: float = 2_000.0
    num_frequency_points: int = 4_000
    laser_frequency_noise_hz_per_sqrt_hz: NoiseModel = field(default_factory=NoiseModel)
    mirror_acceleration_noise_mps2_per_sqrt_hz: NoiseModel = field(default_factory=NoiseModel)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NoiseParameters":
        return cls(
            f_min_hz=float(data.get("f_min_hz", 0.2)),
            f_max_hz=float(data.get("f_max_hz", 2_000.0)),
            num_frequency_points=int(data.get("num_frequency_points", 4_000)),
            laser_frequency_noise_hz_per_sqrt_hz=NoiseModel.from_dict(
                data.get("laser_frequency_noise_hz_per_sqrt_hz", {})
            ),
            mirror_acceleration_noise_mps2_per_sqrt_hz=NoiseModel.from_dict(
                data.get("mirror_acceleration_noise_mps2_per_sqrt_hz", {})
            ),
        )


@dataclass(frozen=True)
class SimulationParameters:
    shots_per_phase: int = 400
    n_phase_points: int = 121
    scan_start_rad: float = 0.0
    scan_stop_rad: float = PI2
    random_seed: int = 7
    output_prefix: str = "outputs/bragg_demo"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimulationParameters":
        return cls(
            shots_per_phase=int(data.get("shots_per_phase", 400)),
            n_phase_points=int(data.get("n_phase_points", 121)),
            scan_start_rad=float(data.get("scan_start_rad", 0.0)),
            scan_stop_rad=float(data.get("scan_stop_rad", PI2)),
            random_seed=int(data.get("random_seed", 7)),
            output_prefix=str(data.get("output_prefix", "outputs/bragg_demo")),
        )


@dataclass(frozen=True)
class BraggSimulationConfig:
    interferometer: InterferometerParameters
    beam_splitter_1: PulseParameters
    mirror: PulseParameters
    beam_splitter_2: PulseParameters
    noise: NoiseParameters
    simulation: SimulationParameters

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BraggSimulationConfig":
        return cls(
            interferometer=InterferometerParameters.from_dict(data.get("interferometer", {})),
            beam_splitter_1=PulseParameters.from_dict(data.get("beam_splitter_1", {})),
            mirror=PulseParameters.from_dict(data.get("mirror", {})),
            beam_splitter_2=PulseParameters.from_dict(data.get("beam_splitter_2", {})),
            noise=NoiseParameters.from_dict(data.get("noise", {})),
            simulation=SimulationParameters.from_dict(data.get("simulation", {})),
        )


def default_config() -> BraggSimulationConfig:
    return BraggSimulationConfig(
        interferometer=InterferometerParameters(
            bragg_order=4,
            wavelength_m=780e-9,
            pulse_separation_s=50e-3,
            effective_acceleration_mps2=0.0,
            additional_phase_offset_rad=0.2,
        ),
        beam_splitter_1=PulseParameters(
            transfer_probability=0.48,
            loss_probability=0.03,
            diffraction_phase_rad=0.00,
            transfer_jitter_std=0.015,
            phase_jitter_std_rad=0.02,
        ),
        mirror=PulseParameters(
            transfer_probability=0.93,
            loss_probability=0.05,
            diffraction_phase_rad=0.08,
            transfer_jitter_std=0.020,
            phase_jitter_std_rad=0.03,
        ),
        beam_splitter_2=PulseParameters(
            transfer_probability=0.46,
            loss_probability=0.03,
            diffraction_phase_rad=0.02,
            transfer_jitter_std=0.015,
            phase_jitter_std_rad=0.02,
        ),
        noise=NoiseParameters(
            f_min_hz=0.2,
            f_max_hz=2_000.0,
            num_frequency_points=4_000,
            laser_frequency_noise_hz_per_sqrt_hz=NoiseModel(
                white_psd_db=legacy_asd_amplitude_to_psd_db(0.10),
                flicker_psd_1hz_db=legacy_asd_amplitude_to_psd_db(0.05),
                random_walk_psd_1hz_db=legacy_asd_amplitude_to_psd_db(0.01),
                peaks=(
                    LorentzianPeak(center_hz=60.0, width_hz=4.0, psd_db=-20.0),
                    LorentzianPeak(center_hz=180.0, width_hz=10.0, psd_db=-21.93820026016113),
                ),
            ),
            mirror_acceleration_noise_mps2_per_sqrt_hz=NoiseModel(
                white_psd_db=legacy_asd_amplitude_to_psd_db(2.0e-6),
                flicker_psd_1hz_db=legacy_asd_amplitude_to_psd_db(1.0e-6),
                random_walk_psd_1hz_db=legacy_asd_amplitude_to_psd_db(1.5e-7),
                peaks=(
                    LorentzianPeak(center_hz=12.0, width_hz=1.5, psd_db=-102.49877473216599),
                    LorentzianPeak(center_hz=38.0, width_hz=3.0, psd_db=-110.45757490560675),
                ),
            ),
        ),
        simulation=SimulationParameters(
            shots_per_phase=500,
            n_phase_points=121,
            scan_start_rad=0.0,
            scan_stop_rad=PI2,
            random_seed=7,
            output_prefix="outputs/bragg_demo",
        ),
    )


def coherent_transfer_probability(
    omega_eff_rad_s: float,
    duration_s: float,
    detuning_rad_s: float = 0.0,
) -> float:
    omega_rabi = math.hypot(omega_eff_rad_s, detuning_rad_s)
    if omega_rabi == 0.0:
        return 0.0
    return (omega_eff_rad_s**2 / omega_rabi**2) * math.sin(0.5 * omega_rabi * duration_s) ** 2


def legacy_asd_amplitude_to_psd_db(amplitude: float) -> float:
    if amplitude <= 0.0:
        return NEG_INF_DB
    return 10.0 * math.log10(amplitude**2)


def linear_psd_from_db(psd_db: float) -> float:
    return 10.0 ** (psd_db / 10.0)


def noise_term_db_from_dict(data: dict[str, Any], new_key: str, legacy_key: str) -> float:
    if new_key in data:
        return float(data[new_key])
    if legacy_key in data:
        return legacy_asd_amplitude_to_psd_db(float(data[legacy_key]))
    return NEG_INF_DB


def composite_asd(f_hz: np.ndarray, model: NoiseModel, f_floor_hz: float) -> np.ndarray:
    f_safe = np.maximum(f_hz, f_floor_hz)
    total_psd = (
        linear_psd_from_db(model.white_psd_db)
        + linear_psd_from_db(model.flicker_psd_1hz_db) / f_safe
        + linear_psd_from_db(model.random_walk_psd_1hz_db) / (f_safe**2)
    )
    for peak in model.peaks:
        width = max(peak.width_hz, 1e-12)
        peak_psd_linear = 10.0 ** (peak.psd_db / 10.0)
        total_psd += peak_psd_linear / (1.0 + ((f_hz - peak.center_hz) / width) ** 2)
    return np.sqrt(total_psd)


def make_frequency_grid(noise: NoiseParameters) -> np.ndarray:
    return np.logspace(
        math.log10(noise.f_min_hz),
        math.log10(noise.f_max_hz),
        noise.num_frequency_points,
    )


def phase_transfer_function(f_hz: np.ndarray, pulse_separation_s: float) -> np.ndarray:
    return np.abs(
        1.0
        - 2.0 * np.exp(-1j * PI2 * f_hz * pulse_separation_s)
        + np.exp(-1j * 2.0 * PI2 * f_hz * pulse_separation_s)
    )


def effective_wavevector_m_inv(cfg: BraggSimulationConfig) -> float:
    k = PI2 / cfg.interferometer.wavelength_m
    return 2.0 * cfg.interferometer.bragg_order * k


def laser_phase_psd_rad2_per_hz(cfg: BraggSimulationConfig, f_hz: np.ndarray) -> np.ndarray:
    laser_asd = composite_asd(
        f_hz,
        cfg.noise.laser_frequency_noise_hz_per_sqrt_hz,
        cfg.noise.f_min_hz,
    )
    f_safe = np.maximum(f_hz, cfg.noise.f_min_hz)
    return (cfg.interferometer.bragg_order**2) * (laser_asd**2) / (f_safe**2)


def vibration_phase_psd_rad2_per_hz(cfg: BraggSimulationConfig, f_hz: np.ndarray) -> np.ndarray:
    accel_asd = composite_asd(
        f_hz,
        cfg.noise.mirror_acceleration_noise_mps2_per_sqrt_hz,
        cfg.noise.f_min_hz,
    )
    omega = PI2 * np.maximum(f_hz, cfg.noise.f_min_hz)
    return (effective_wavevector_m_inv(cfg) ** 2) * (accel_asd**2) / (omega**4)


def phase_noise_std_from_psd(
    f_hz: np.ndarray,
    phase_psd_rad2_per_hz: np.ndarray,
    pulse_separation_s: float,
) -> tuple[float, np.ndarray]:
    transfer = phase_transfer_function(f_hz, pulse_separation_s)
    integrand = transfer**2 * phase_psd_rad2_per_hz
    variance = np.trapz(integrand, f_hz)
    return math.sqrt(max(variance, 0.0)), integrand


def sample_transfer_probability(base: float, jitter_std: float, rng: np.random.Generator) -> float:
    if jitter_std <= 0.0:
        return float(np.clip(base, 0.0, 1.0))
    return float(np.clip(rng.normal(base, jitter_std), 0.0, 1.0))


def sample_phase(base: float, jitter_std: float, rng: np.random.Generator) -> float:
    if jitter_std <= 0.0:
        return base
    return float(rng.normal(base, jitter_std))


def pulse_matrix(transfer_probability: float, phase_rad: float, loss_probability: float) -> np.ndarray:
    p = float(np.clip(transfer_probability, 0.0, 1.0))
    loss = float(np.clip(loss_probability, 0.0, 0.999999))
    stay = math.sqrt(max(0.0, 1.0 - p))
    move = math.sqrt(p)
    phase = np.exp(1j * phase_rad)
    return math.sqrt(1.0 - loss) * np.array(
        [
            [stay, -1j * np.conjugate(phase) * move],
            [-1j * phase * move, stay],
        ],
        dtype=np.complex128,
    )


def base_interferometer_phase_rad(cfg: BraggSimulationConfig) -> float:
    return (
        effective_wavevector_m_inv(cfg)
        * cfg.interferometer.effective_acceleration_mps2
        * cfg.interferometer.pulse_separation_s**2
        + cfg.interferometer.additional_phase_offset_rad
    )


def simulate_single_shot(
    cfg: BraggSimulationConfig,
    total_interferometer_phase_rad: float,
    rng: np.random.Generator,
) -> tuple[float, float, float]:
    pulse1 = cfg.beam_splitter_1
    pulse2 = cfg.mirror
    pulse3 = cfg.beam_splitter_2

    u1 = pulse_matrix(
        transfer_probability=sample_transfer_probability(
            pulse1.transfer_probability,
            pulse1.transfer_jitter_std,
            rng,
        ),
        phase_rad=sample_phase(
            pulse1.diffraction_phase_rad,
            pulse1.phase_jitter_std_rad,
            rng,
        ),
        loss_probability=pulse1.loss_probability,
    )
    u2 = pulse_matrix(
        transfer_probability=sample_transfer_probability(
            pulse2.transfer_probability,
            pulse2.transfer_jitter_std,
            rng,
        ),
        phase_rad=sample_phase(
            pulse2.diffraction_phase_rad,
            pulse2.phase_jitter_std_rad,
            rng,
        ),
        loss_probability=pulse2.loss_probability,
    )
    u3 = pulse_matrix(
        transfer_probability=sample_transfer_probability(
            pulse3.transfer_probability,
            pulse3.transfer_jitter_std,
            rng,
        ),
        phase_rad=sample_phase(
            pulse3.diffraction_phase_rad,
            pulse3.phase_jitter_std_rad,
            rng,
        )
        + total_interferometer_phase_rad,
        loss_probability=pulse3.loss_probability,
    )

    state = np.array([1.0 + 0.0j, 0.0 + 0.0j], dtype=np.complex128)
    state = u3 @ (u2 @ (u1 @ state))

    port_a = float(np.abs(state[0]) ** 2)
    port_b = float(np.abs(state[1]) ** 2)
    remaining = port_a + port_b
    return port_a, port_b, max(0.0, 1.0 - remaining)


def fit_cosine(scan_phase_rad: np.ndarray, y: np.ndarray, bragg_order: int) -> dict[str, float]:
    basis = np.column_stack(
        [
            np.ones_like(scan_phase_rad),
            np.cos(bragg_order * scan_phase_rad),
            np.sin(bragg_order * scan_phase_rad),
        ]
    )
    coeffs, *_ = np.linalg.lstsq(basis, y, rcond=None)
    offset, cos_coeff, sin_coeff = coeffs
    amplitude = float(math.hypot(cos_coeff, sin_coeff))
    phase_offset = float(math.atan2(-sin_coeff, cos_coeff))
    contrast = float(np.max(y) - np.min(y))
    return {
        "offset": float(offset),
        "amplitude": amplitude,
        "phase_offset_rad": phase_offset,
        "contrast": contrast,
    }


def simulate_fringe(cfg: BraggSimulationConfig) -> dict[str, Any]:
    rng = np.random.default_rng(cfg.simulation.random_seed)
    f_hz = make_frequency_grid(cfg.noise)
    laser_psd = laser_phase_psd_rad2_per_hz(cfg, f_hz)
    vibration_psd = vibration_phase_psd_rad2_per_hz(cfg, f_hz)

    laser_phase_std_rad, laser_integrand = phase_noise_std_from_psd(
        f_hz,
        laser_psd,
        cfg.interferometer.pulse_separation_s,
    )
    vibration_phase_std_rad, vibration_integrand = phase_noise_std_from_psd(
        f_hz,
        vibration_psd,
        cfg.interferometer.pulse_separation_s,
    )

    scan_phase_rad = np.linspace(
        cfg.simulation.scan_start_rad,
        cfg.simulation.scan_stop_rad,
        cfg.simulation.n_phase_points,
    )
    base_phase = base_interferometer_phase_rad(cfg)

    port_b_abs_mean = np.zeros_like(scan_phase_rad)
    port_b_abs_std = np.zeros_like(scan_phase_rad)
    port_b_norm_mean = np.zeros_like(scan_phase_rad)
    port_b_norm_std = np.zeros_like(scan_phase_rad)
    loss_mean = np.zeros_like(scan_phase_rad)

    for index, optical_phase in enumerate(scan_phase_rad):
        noisy_abs = np.zeros(cfg.simulation.shots_per_phase)
        noisy_norm = np.zeros(cfg.simulation.shots_per_phase)
        losses = np.zeros(cfg.simulation.shots_per_phase)

        for shot in range(cfg.simulation.shots_per_phase):
            total_phase = (
                base_phase
                + cfg.interferometer.bragg_order * optical_phase
                + rng.normal(0.0, laser_phase_std_rad)
                + rng.normal(0.0, vibration_phase_std_rad)
            )
            port_a, port_b, loss = simulate_single_shot(cfg, total_phase, rng)
            remaining = port_a + port_b
            noisy_abs[shot] = port_b
            noisy_norm[shot] = port_b / remaining if remaining > 1e-12 else 0.0
            losses[shot] = loss

        port_b_abs_mean[index] = noisy_abs.mean()
        port_b_abs_std[index] = noisy_abs.std(ddof=1)
        port_b_norm_mean[index] = noisy_norm.mean()
        port_b_norm_std[index] = noisy_norm.std(ddof=1)
        loss_mean[index] = losses.mean()

    fit = fit_cosine(
        scan_phase_rad=scan_phase_rad,
        y=port_b_norm_mean,
        bragg_order=cfg.interferometer.bragg_order,
    )

    return {
        "scan_phase_rad": scan_phase_rad,
        "port_b_abs_mean": port_b_abs_mean,
        "port_b_abs_std": port_b_abs_std,
        "port_b_norm_mean": port_b_norm_mean,
        "port_b_norm_std": port_b_norm_std,
        "loss_mean": loss_mean,
        "frequency_hz": f_hz,
        "laser_phase_psd_rad2_per_hz": laser_psd,
        "vibration_phase_psd_rad2_per_hz": vibration_psd,
        "laser_integrand_rad2_per_hz": laser_integrand,
        "vibration_integrand_rad2_per_hz": vibration_integrand,
        "laser_phase_std_rad": laser_phase_std_rad,
        "vibration_phase_std_rad": vibration_phase_std_rad,
        "fit": fit,
    }


def config_to_dict(cfg: BraggSimulationConfig) -> dict[str, Any]:
    return asdict(cfg)


def load_config(path: Path | str | None) -> BraggSimulationConfig:
    if path is None:
        return default_config()
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return BraggSimulationConfig.from_dict(data)


def save_config(cfg: BraggSimulationConfig, path: Path | str) -> Path:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config_to_dict(cfg), indent=2), encoding="utf-8")
    return config_path


def update_output_prefix(cfg: BraggSimulationConfig, output_prefix: str) -> BraggSimulationConfig:
    return replace(cfg, simulation=replace(cfg.simulation, output_prefix=output_prefix))


def save_csv(output_prefix: Path, results: dict[str, Any]) -> Path:
    csv_path = output_prefix.with_suffix(".csv")
    data = np.column_stack(
        [
            results["scan_phase_rad"],
            results["port_b_abs_mean"],
            results["port_b_abs_std"],
            results["port_b_norm_mean"],
            results["port_b_norm_std"],
            results["loss_mean"],
        ]
    )
    header = (
        "scan_phase_rad,"
        "port_b_abs_mean,"
        "port_b_abs_std,"
        "port_b_norm_mean,"
        "port_b_norm_std,"
        "loss_mean"
    )
    np.savetxt(csv_path, data, delimiter=",", header=header, comments="")
    return csv_path


def summary_payload(cfg: BraggSimulationConfig, results: dict[str, Any]) -> dict[str, Any]:
    return {
        "config": config_to_dict(cfg),
        "laser_phase_std_rad": results["laser_phase_std_rad"],
        "vibration_phase_std_rad": results["vibration_phase_std_rad"],
        "fit": results["fit"],
    }


def save_summary(output_prefix: Path, cfg: BraggSimulationConfig, results: dict[str, Any]) -> Path:
    summary_path = output_prefix.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary_payload(cfg, results), indent=2), encoding="utf-8")
    return summary_path


def save_plot(output_prefix: Path, cfg: BraggSimulationConfig, results: dict[str, Any]) -> Path | None:
    if plt is None:
        return None

    fig, axes = plt.subplots(2, 1, figsize=(9, 8), constrained_layout=True)
    plot_results_on_axes(cfg, results, axes)
    plot_path = output_prefix.with_suffix(".png")
    fig.savefig(plot_path, dpi=180)
    plt.close(fig)
    return plot_path


def plot_results_on_axes(
    cfg: BraggSimulationConfig,
    results: dict[str, Any],
    axes: Any,
) -> None:
    scan = results["scan_phase_rad"]
    fit = results["fit"]
    fitted = fit["offset"] + fit["amplitude"] * np.cos(
        cfg.interferometer.bragg_order * scan + fit["phase_offset_rad"]
    )

    fringe_axis, noise_axis = axes
    fringe_axis.clear()
    fringe_axis.plot(scan, results["port_b_norm_mean"], color="tab:blue", label="Monte Carlo fringe")
    fringe_axis.fill_between(
        scan,
        results["port_b_norm_mean"] - results["port_b_norm_std"],
        results["port_b_norm_mean"] + results["port_b_norm_std"],
        color="tab:blue",
        alpha=0.18,
        linewidth=0.0,
        label="shot scatter",
    )
    fringe_axis.plot(scan, fitted, color="tab:red", linestyle="--", label="cosine fit")
    fringe_axis.set_xlabel("Scanned optical phase phi0 [rad]")
    fringe_axis.set_ylabel("Normalised upper-port population")
    fringe_axis.set_title(
        "Bragg-Mach-Zehnder fringe\n"
        f"peak-to-peak contrast={fit['contrast']:.3f}, phase offset={fit['phase_offset_rad']:.3f} rad"
    )
    fringe_axis.legend()
    fringe_axis.grid(alpha=0.25)

    freq = results["frequency_hz"]
    noise_axis.clear()
    noise_axis.loglog(
        freq,
        results["laser_integrand_rad2_per_hz"],
        color="tab:green",
        label="laser-frequency noise contribution",
    )
    noise_axis.loglog(
        freq,
        results["vibration_integrand_rad2_per_hz"],
        color="tab:orange",
        label="mirror-vibration contribution",
    )
    noise_axis.set_xlabel("Fourier frequency [Hz]")
    noise_axis.set_ylabel("|H(f)|^2 S_phi(f) [rad^2/Hz]")
    noise_axis.set_title("Phase-noise weighting by interferometer transfer function")
    noise_axis.legend()
    noise_axis.grid(alpha=0.25, which="both")


def save_all_outputs(
    cfg: BraggSimulationConfig,
    results: dict[str, Any],
    output_prefix: str | Path | None = None,
) -> dict[str, Path | None]:
    prefix = Path(output_prefix if output_prefix is not None else cfg.simulation.output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    return {
        "csv": save_csv(prefix, results),
        "summary": save_summary(prefix, cfg, results),
        "plot": save_plot(prefix, cfg, results),
    }


def format_result_summary(results: dict[str, Any]) -> str:
    fit = results["fit"]
    return "\n".join(
        [
            f"Laser phase sigma: {results['laser_phase_std_rad']:.6f} rad",
            f"Mirror vibration sigma: {results['vibration_phase_std_rad']:.6f} rad",
            f"Fringe offset: {fit['offset']:.6f}",
            f"Fringe amplitude: {fit['amplitude']:.6f}",
            f"Normalised peak-to-peak contrast: {fit['contrast']:.6f}",
            f"Phase offset: {fit['phase_offset_rad']:.6f} rad",
        ]
    )
