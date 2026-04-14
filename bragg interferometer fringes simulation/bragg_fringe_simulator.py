#!/usr/bin/env python3
from __future__ import annotations

import argparse
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


@dataclass(frozen=True)
class LorentzianPeak:
    center_hz: float
    width_hz: float
    amplitude: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LorentzianPeak":
        return cls(
            center_hz=float(data["center_hz"]),
            width_hz=float(data["width_hz"]),
            amplitude=float(data["amplitude"]),
        )


@dataclass(frozen=True)
class NoiseModel:
    white: float = 0.0
    flicker: float = 0.0
    random_walk: float = 0.0
    peaks: tuple[LorentzianPeak, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NoiseModel":
        peaks = tuple(LorentzianPeak.from_dict(item) for item in data.get("peaks", []))
        return cls(
            white=float(data.get("white", 0.0)),
            flicker=float(data.get("flicker", 0.0)),
            random_walk=float(data.get("random_walk", 0.0)),
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
                white=0.10,
                flicker=0.05,
                random_walk=0.01,
                peaks=(
                    LorentzianPeak(center_hz=60.0, width_hz=4.0, amplitude=0.10),
                    LorentzianPeak(center_hz=180.0, width_hz=10.0, amplitude=0.08),
                ),
            ),
            mirror_acceleration_noise_mps2_per_sqrt_hz=NoiseModel(
                white=2.0e-6,
                flicker=1.0e-6,
                random_walk=1.5e-7,
                peaks=(
                    LorentzianPeak(center_hz=12.0, width_hz=1.5, amplitude=7.5e-6),
                    LorentzianPeak(center_hz=38.0, width_hz=3.0, amplitude=3.0e-6),
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


def composite_asd(f_hz: np.ndarray, model: NoiseModel, f_floor_hz: float) -> np.ndarray:
    f_safe = np.maximum(f_hz, f_floor_hz)
    asd_sq = (
        model.white**2
        + (model.flicker / np.sqrt(f_safe)) ** 2
        + (model.random_walk / f_safe) ** 2
    )
    for peak in model.peaks:
        width = max(peak.width_hz, 1e-12)
        asd_sq += peak.amplitude**2 / (1.0 + ((f_hz - peak.center_hz) / width) ** 2)
    return np.sqrt(asd_sq)


def make_frequency_grid(noise: NoiseParameters) -> np.ndarray:
    return np.logspace(
        math.log10(noise.f_min_hz),
        math.log10(noise.f_max_hz),
        noise.num_frequency_points,
    )


def phase_transfer_function(f_hz: np.ndarray, pulse_separation_s: float) -> np.ndarray:
    return np.abs(1.0 - 2.0 * np.exp(-1j * PI2 * f_hz * pulse_separation_s) + np.exp(-1j * 2.0 * PI2 * f_hz * pulse_separation_s))


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
    contrast = float(amplitude / offset) if abs(offset) > 1e-12 else float("nan")
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


def save_summary(output_prefix: Path, cfg: BraggSimulationConfig, results: dict[str, Any]) -> Path:
    summary_path = output_prefix.with_suffix(".summary.json")
    summary = {
        "config": asdict(cfg),
        "laser_phase_std_rad": results["laser_phase_std_rad"],
        "vibration_phase_std_rad": results["vibration_phase_std_rad"],
        "fit": results["fit"],
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary_path


def save_plot(output_prefix: Path, cfg: BraggSimulationConfig, results: dict[str, Any]) -> Path | None:
    if plt is None:
        return None

    fig, axes = plt.subplots(2, 1, figsize=(9, 8), constrained_layout=True)

    scan = results["scan_phase_rad"]
    fit = results["fit"]
    fitted = fit["offset"] + fit["amplitude"] * np.cos(
        cfg.interferometer.bragg_order * scan + fit["phase_offset_rad"]
    )

    axes[0].plot(scan, results["port_b_norm_mean"], color="tab:blue", label="Monte Carlo fringe")
    axes[0].fill_between(
        scan,
        results["port_b_norm_mean"] - results["port_b_norm_std"],
        results["port_b_norm_mean"] + results["port_b_norm_std"],
        color="tab:blue",
        alpha=0.18,
        linewidth=0.0,
        label="shot scatter",
    )
    axes[0].plot(scan, fitted, color="tab:red", linestyle="--", label="cosine fit")
    axes[0].set_xlabel("Scanned optical phase $\\phi_0$ [rad]")
    axes[0].set_ylabel("Normalised upper-port population")
    axes[0].set_title(
        "Bragg-Mach-Zehnder fringe\n"
        f"contrast={fit['contrast']:.3f}, phase offset={fit['phase_offset_rad']:.3f} rad"
    )
    axes[0].legend()
    axes[0].grid(alpha=0.25)

    freq = results["frequency_hz"]
    axes[1].loglog(
        freq,
        results["laser_integrand_rad2_per_hz"],
        color="tab:green",
        label="laser-frequency noise contribution",
    )
    axes[1].loglog(
        freq,
        results["vibration_integrand_rad2_per_hz"],
        color="tab:orange",
        label="mirror-vibration contribution",
    )
    axes[1].set_xlabel("Fourier frequency [Hz]")
    axes[1].set_ylabel(r"$|H(f)|^2 S_\phi(f)$ [rad$^2$/Hz]")
    axes[1].set_title("Phase-noise weighting by interferometer transfer function")
    axes[1].legend()
    axes[1].grid(alpha=0.25, which="both")

    plot_path = output_prefix.with_suffix(".png")
    fig.savefig(plot_path, dpi=180)
    plt.close(fig)
    return plot_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monte Carlo Bragg atom-interferometer fringe simulator with pulse imperfections and phase noise."
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional JSON config file. If omitted, the built-in example config is used.",
    )
    parser.add_argument(
        "--dump-default-config",
        type=Path,
        help="Write the default config as JSON and exit.",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        help="Override the output prefix from the config.",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip PNG generation even if matplotlib is available.",
    )
    return parser.parse_args()


def load_config(config_path: Path | None) -> BraggSimulationConfig:
    if config_path is None:
        return default_config()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return BraggSimulationConfig.from_dict(data)


def main() -> None:
    args = parse_args()

    if args.dump_default_config is not None:
        cfg = default_config()
        args.dump_default_config.write_text(
            json.dumps(asdict(cfg), indent=2),
            encoding="utf-8",
        )
        print(f"Wrote default config to {args.dump_default_config}")
        return

    cfg = load_config(args.config)
    if args.output_prefix:
        cfg = replace(
            cfg,
            simulation=replace(cfg.simulation, output_prefix=args.output_prefix),
        )

    output_prefix = Path(cfg.simulation.output_prefix)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)

    results = simulate_fringe(cfg)
    csv_path = save_csv(output_prefix, results)
    summary_path = save_summary(output_prefix, cfg, results)
    plot_path = None if args.no_plot else save_plot(output_prefix, cfg, results)

    print("Bragg fringe simulation finished.")
    print(f"CSV: {csv_path}")
    print(f"Summary: {summary_path}")
    if plot_path is not None:
        print(f"Plot: {plot_path}")
    elif not args.no_plot:
        print("Plot skipped because matplotlib is not installed.")
    print(
        "Noise phase sigma: "
        f"laser={results['laser_phase_std_rad']:.4f} rad, "
        f"vibration={results['vibration_phase_std_rad']:.4f} rad"
    )
    print(
        "Fitted normalised fringe: "
        f"contrast={results['fit']['contrast']:.4f}, "
        f"phase_offset={results['fit']['phase_offset_rad']:.4f} rad"
    )


if __name__ == "__main__":
    main()
