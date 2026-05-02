from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


AMU_KG = 1.66053906660e-27
PLANCK_J_S = 6.62607015e-34
BOHR_MAGNETON_J_T = 9.2740100783e-24
RB87_MASS_KG = 86.9091805310 * AMU_KG
RB87_D2_WAVELENGTH_M = 780.241209e-9
RB87_D2_LINEWIDTH_HZ = 6.065e6
RB87_F2_G_FACTOR_ABS = 0.5


@dataclass(frozen=True)
class AtomConfig:
    mass_kg: float = RB87_MASS_KG
    wavelength_m: float = RB87_D2_WAVELENGTH_M
    linewidth_hz: float = RB87_D2_LINEWIDTH_HZ
    ground_state_g_factor_abs: float = RB87_F2_G_FACTOR_ABS


@dataclass(frozen=True)
class MolassesConfig:
    initial_temperature_uK: float = 40.0
    zero_field_temperature_uK: float = 2
    failure_temperature_uK: float = 80.0
    molasses_duration_ms: float = 5.0
    time_step_us: float = 20.0
    zero_field_cooling_time_ms: float = 1.2
    detuning_mhz: float = -15.0
    saturation_parameter_per_beam: float = 0.20
    number_of_beams: int = 6
    optical_pumping_width_scale: float = 1.0
    minimum_relative_efficiency: float = 0.03
    magnetic_width_mG_override: float | None = None


@dataclass(frozen=True)
class FieldConfig:
    static_stray_field_mG: tuple[float, float, float] = (0, -60, 0)
    mot_switch_off_field_mG: tuple[float, float, float] = (0, 35, 35.0)
    mot_decay_tau_ms: float = 0.5


@dataclass(frozen=True)
class CoilConfig:
    coil_matrix_mG_per_unit: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ] = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )


@dataclass(frozen=True)
class AxisScan:
    start: float
    stop: float
    points: int

    def values(self) -> np.ndarray:
        return np.linspace(self.start, self.stop, self.points)


@dataclass(frozen=True)
class ScanConfig:
    x: AxisScan = AxisScan(-120.0, 120.0, 25)
    y: AxisScan = AxisScan(-120.0, 120.0, 25)
    z: AxisScan = AxisScan(-120.0, 120.0, 25)


@dataclass(frozen=True)
class OutputConfig:
    directory: str = "outputs"
    prefix: str = "rb87_pgc_bias_scan"


@dataclass(frozen=True)
class SimulationConfig:
    atom: AtomConfig = AtomConfig()
    molasses: MolassesConfig = MolassesConfig()
    fields: FieldConfig = FieldConfig()
    coils: CoilConfig = CoilConfig()
    scan: ScanConfig = ScanConfig()
    output: OutputConfig = OutputConfig()

    @classmethod
    def from_dict(cls, data: dict) -> "SimulationConfig":
        return cls(
            atom=AtomConfig(**data.get("atom", {})),
            molasses=MolassesConfig(**data.get("molasses", {})),
            fields=FieldConfig(
                static_stray_field_mG=tuple(data.get("fields", {}).get("static_stray_field_mG", FieldConfig.static_stray_field_mG)),
                mot_switch_off_field_mG=tuple(data.get("fields", {}).get("mot_switch_off_field_mG", FieldConfig.mot_switch_off_field_mG)),
                mot_decay_tau_ms=data.get("fields", {}).get("mot_decay_tau_ms", FieldConfig.mot_decay_tau_ms),
            ),
            coils=CoilConfig(
                coil_matrix_mG_per_unit=tuple(
                    tuple(row) for row in data.get("coils", {}).get("coil_matrix_mG_per_unit", CoilConfig.coil_matrix_mG_per_unit)
                )
            ),
            scan=ScanConfig(
                x=AxisScan(**data.get("scan", {}).get("x", asdict(ScanConfig().x))),
                y=AxisScan(**data.get("scan", {}).get("y", asdict(ScanConfig().y))),
                z=AxisScan(**data.get("scan", {}).get("z", asdict(ScanConfig().z))),
            ),
            output=OutputConfig(**data.get("output", {})),
        )


def load_config(path: Path | None) -> SimulationConfig:
    if path is None:
        return SimulationConfig()
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return SimulationConfig.from_dict(data)


def save_resolved_config(config: SimulationConfig, output_dir: Path, prefix: str) -> Path:
    path = output_dir / f"{prefix}_resolved_config.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(config), handle, indent=2)
    return path


def magnetic_sensitivity_hz_per_mG(g_factor_abs: float) -> float:
    return g_factor_abs * BOHR_MAGNETON_J_T / PLANCK_J_S * 1.0e-7


def optical_pumping_rate_hz(config: SimulationConfig) -> float:
    molasses = config.molasses
    linewidth_hz = config.atom.linewidth_hz
    total_s = max(molasses.saturation_parameter_per_beam * molasses.number_of_beams, 1.0e-9)
    detuning_hz = abs(molasses.detuning_mhz) * 1.0e6
    denominator = 1.0 + total_s + 4.0 * (detuning_hz / linewidth_hz) ** 2
    return 0.5 * linewidth_hz * total_s / denominator


def magnetic_width_mG(config: SimulationConfig) -> float:
    override = config.molasses.magnetic_width_mG_override
    if override is not None:
        return max(float(override), 1.0e-6)
    sensitivity = magnetic_sensitivity_hz_per_mG(config.atom.ground_state_g_factor_abs)
    width = config.molasses.optical_pumping_width_scale * optical_pumping_rate_hz(config) / sensitivity
    return max(width, 1.0e-6)


def time_axis_ms(config: SimulationConfig) -> np.ndarray:
    dt_ms = config.molasses.time_step_us * 1.0e-3
    n_steps = max(int(np.ceil(config.molasses.molasses_duration_ms / dt_ms)), 1)
    return np.linspace(0.0, config.molasses.molasses_duration_ms, n_steps + 1)


def residual_field_trace_mG(config: SimulationConfig, setpoint_xyz: np.ndarray, time_ms: np.ndarray) -> np.ndarray:
    static_field = np.asarray(config.fields.static_stray_field_mG, dtype=float)
    decay_field = np.asarray(config.fields.mot_switch_off_field_mG, dtype=float)
    coil_matrix = np.asarray(config.coils.coil_matrix_mG_per_unit, dtype=float)
    compensation_field = coil_matrix @ setpoint_xyz

    if config.fields.mot_decay_tau_ms > 0.0:
        decay_scale = np.exp(-time_ms / config.fields.mot_decay_tau_ms)
    else:
        decay_scale = np.zeros_like(time_ms)

    return static_field + compensation_field + decay_scale[:, None] * decay_field


def simulate_one_setting(config: SimulationConfig, setpoint_xyz: np.ndarray) -> dict:
    time_ms = time_axis_ms(config)
    dt_ms = np.diff(time_ms)
    field_trace = residual_field_trace_mG(config, setpoint_xyz, time_ms)
    field_norm_mG = np.linalg.norm(field_trace, axis=1)

    width_mG = magnetic_width_mG(config)
    raw_efficiency = 1.0 / (1.0 + (field_norm_mG / width_mG) ** 2)
    clipped_efficiency = np.clip(
        raw_efficiency,
        config.molasses.minimum_relative_efficiency,
        1.0,
    )

    zero_field_temp = config.molasses.zero_field_temperature_uK
    failure_temp = max(config.molasses.failure_temperature_uK, zero_field_temp)
    equilibrium_temp = zero_field_temp + (failure_temp - zero_field_temp) * (1.0 - raw_efficiency)
    cooling_tau_ms = config.molasses.zero_field_cooling_time_ms / clipped_efficiency

    temperature_uK = np.empty_like(time_ms)
    temperature_uK[0] = config.molasses.initial_temperature_uK
    for idx, delta_t in enumerate(dt_ms):
        slope = -(temperature_uK[idx] - equilibrium_temp[idx]) / cooling_tau_ms[idx]
        temperature_uK[idx + 1] = temperature_uK[idx] + slope * delta_t

    denominator = config.molasses.initial_temperature_uK - zero_field_temp
    if abs(denominator) < 1.0e-12:
        cooling_efficiency = np.nan
    else:
        cooling_efficiency = (config.molasses.initial_temperature_uK - temperature_uK[-1]) / denominator

    return {
        "setpoint_xyz": setpoint_xyz.copy(),
        "time_ms": time_ms,
        "field_trace_mG": field_trace,
        "field_norm_mG": field_norm_mG,
        "relative_efficiency_trace": raw_efficiency,
        "temperature_uK": temperature_uK,
        "final_temperature_uK": float(temperature_uK[-1]),
        "cooling_efficiency": float(cooling_efficiency),
        "mean_field_mG": float(field_norm_mG.mean()),
        "initial_field_mG": float(field_norm_mG[0]),
        "final_field_mG": float(field_norm_mG[-1]),
        "mean_relative_efficiency": float(raw_efficiency.mean()),
        "magnetic_width_mG": float(width_mG),
    }


def run_scan(config: SimulationConfig) -> dict:
    x_values = config.scan.x.values()
    y_values = config.scan.y.values()
    z_values = config.scan.z.values()

    temp_grid = np.empty((len(z_values), len(y_values), len(x_values)))
    efficiency_grid = np.empty_like(temp_grid)
    mean_field_grid = np.empty_like(temp_grid)
    records: list[dict] = []

    best_result = None
    best_indices = None

    for iz, z_value in enumerate(z_values):
        for iy, y_value in enumerate(y_values):
            for ix, x_value in enumerate(x_values):
                setpoint = np.array([x_value, y_value, z_value], dtype=float)
                result = simulate_one_setting(config, setpoint)
                temp_grid[iz, iy, ix] = result["final_temperature_uK"]
                efficiency_grid[iz, iy, ix] = result["cooling_efficiency"]
                mean_field_grid[iz, iy, ix] = result["mean_field_mG"]

                record = {
                    "comp_x_unit": float(x_value),
                    "comp_y_unit": float(y_value),
                    "comp_z_unit": float(z_value),
                    "final_temperature_uK": result["final_temperature_uK"],
                    "cooling_efficiency": result["cooling_efficiency"],
                    "mean_field_mG": result["mean_field_mG"],
                    "initial_field_mG": result["initial_field_mG"],
                    "final_field_mG": result["final_field_mG"],
                    "mean_relative_efficiency": result["mean_relative_efficiency"],
                }
                records.append(record)

                if best_result is None or result["final_temperature_uK"] < best_result["final_temperature_uK"]:
                    best_result = result
                    best_indices = (iz, iy, ix)

    if best_result is None or best_indices is None:
        raise RuntimeError("Scan produced no results.")

    return {
        "x_values": x_values,
        "y_values": y_values,
        "z_values": z_values,
        "temp_grid": temp_grid,
        "efficiency_grid": efficiency_grid,
        "mean_field_grid": mean_field_grid,
        "records": records,
        "best_result": best_result,
        "best_indices": best_indices,
    }


def save_scan_csv(records: list[dict], output_dir: Path, prefix: str) -> Path:
    path = output_dir / f"{prefix}_scan.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
    return path


def set_axes_image(ax, image, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.colorbar(image, ax=ax, shrink=0.85)


def make_overview_figure(scan_result: dict, output_dir: Path, prefix: str) -> Path:
    x_values = scan_result["x_values"]
    y_values = scan_result["y_values"]
    z_values = scan_result["z_values"]
    temp_grid = scan_result["temp_grid"]
    best_result = scan_result["best_result"]
    best_iz, best_iy, best_ix = scan_result["best_indices"]

    fig, axes = plt.subplots(2, 2, figsize=(12, 10), constrained_layout=True)

    xy_temp = temp_grid[best_iz, :, :]
    xz_temp = temp_grid[:, best_iy, :]
    yz_temp = temp_grid[:, :, best_ix]

    im_xy = axes[0, 0].imshow(
        xy_temp,
        origin="lower",
        aspect="auto",
        extent=[x_values[0], x_values[-1], y_values[0], y_values[-1]],
        cmap="viridis_r",
    )
    axes[0, 0].plot(best_result["setpoint_xyz"][0], best_result["setpoint_xyz"][1], "ro")
    set_axes_image(
        axes[0, 0],
        im_xy,
        f"Final temperature in XY plane (z = {best_result['setpoint_xyz'][2]:.1f})",
        "Compensation X (arb. unit)",
        "Compensation Y (arb. unit)",
    )

    im_xz = axes[0, 1].imshow(
        xz_temp,
        origin="lower",
        aspect="auto",
        extent=[x_values[0], x_values[-1], z_values[0], z_values[-1]],
        cmap="viridis_r",
    )
    axes[0, 1].plot(best_result["setpoint_xyz"][0], best_result["setpoint_xyz"][2], "ro")
    set_axes_image(
        axes[0, 1],
        im_xz,
        f"Final temperature in XZ plane (y = {best_result['setpoint_xyz'][1]:.1f})",
        "Compensation X (arb. unit)",
        "Compensation Z (arb. unit)",
    )

    im_yz = axes[1, 0].imshow(
        yz_temp,
        origin="lower",
        aspect="auto",
        extent=[y_values[0], y_values[-1], z_values[0], z_values[-1]],
        cmap="viridis_r",
    )
    axes[1, 0].plot(best_result["setpoint_xyz"][1], best_result["setpoint_xyz"][2], "ro")
    set_axes_image(
        axes[1, 0],
        im_yz,
        f"Final temperature in YZ plane (x = {best_result['setpoint_xyz'][0]:.1f})",
        "Compensation Y (arb. unit)",
        "Compensation Z (arb. unit)",
    )

    axes[1, 1].plot(x_values, temp_grid[best_iz, best_iy, :], label="Scan X")
    axes[1, 1].plot(y_values, temp_grid[best_iz, :, best_ix], label="Scan Y")
    axes[1, 1].plot(z_values, temp_grid[:, best_iy, best_ix], label="Scan Z")
    axes[1, 1].axhline(best_result["final_temperature_uK"], color="k", linestyle="--", linewidth=1)
    axes[1, 1].set_title("1D cuts through the best point")
    axes[1, 1].set_xlabel("Compensation value (arb. unit)")
    axes[1, 1].set_ylabel("Final temperature (uK)")
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].legend()

    path = output_dir / f"{prefix}_overview.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def make_dynamics_figure(config: SimulationConfig, best_result: dict, output_dir: Path, prefix: str) -> Path:
    no_comp_result = simulate_one_setting(config, np.zeros(3, dtype=float))

    fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)

    time_ms = best_result["time_ms"]
    best_trace = best_result["field_trace_mG"]
    axes[0, 0].plot(time_ms, best_trace[:, 0], label="Bx")
    axes[0, 0].plot(time_ms, best_trace[:, 1], label="By")
    axes[0, 0].plot(time_ms, best_trace[:, 2], label="Bz")
    axes[0, 0].set_title("Residual field components at best compensation")
    axes[0, 0].set_xlabel("Time after MOT switch-off (ms)")
    axes[0, 0].set_ylabel("Field (mG)")
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].legend()

    axes[0, 1].plot(no_comp_result["time_ms"], no_comp_result["field_norm_mG"], label="No compensation")
    axes[0, 1].plot(best_result["time_ms"], best_result["field_norm_mG"], label="Best compensation")
    axes[0, 1].axhline(best_result["magnetic_width_mG"], color="k", linestyle="--", linewidth=1, label="PGC width")
    axes[0, 1].set_title("Residual field magnitude")
    axes[0, 1].set_xlabel("Time after MOT switch-off (ms)")
    axes[0, 1].set_ylabel("|B| (mG)")
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].legend()

    axes[1, 0].plot(no_comp_result["time_ms"], no_comp_result["relative_efficiency_trace"], label="No compensation")
    axes[1, 0].plot(best_result["time_ms"], best_result["relative_efficiency_trace"], label="Best compensation")
    axes[1, 0].set_title("Instantaneous relative cooling efficiency")
    axes[1, 0].set_xlabel("Time after MOT switch-off (ms)")
    axes[1, 0].set_ylabel("Relative efficiency")
    axes[1, 0].set_ylim(0.0, 1.05)
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].legend()

    axes[1, 1].plot(no_comp_result["time_ms"], no_comp_result["temperature_uK"], label="No compensation")
    axes[1, 1].plot(best_result["time_ms"], best_result["temperature_uK"], label="Best compensation")
    axes[1, 1].set_title("Temperature evolution during optical molasses")
    axes[1, 1].set_xlabel("Time after MOT switch-off (ms)")
    axes[1, 1].set_ylabel("Temperature (uK)")
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].legend()

    path = output_dir / f"{prefix}_dynamics.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def write_summary(scan_result: dict, output_dir: Path, prefix: str) -> Path:
    best_result = scan_result["best_result"]
    best_x, best_y, best_z = best_result["setpoint_xyz"]
    summary_lines = [
        "Rb87 optical molasses bias-coil simulation summary",
        f"Best compensation setpoint: X={best_x:.3f}, Y={best_y:.3f}, Z={best_z:.3f}",
        f"Predicted final temperature: {best_result['final_temperature_uK']:.3f} uK",
        f"Cooling efficiency (0=no cooling, 1=zero-field limit): {best_result['cooling_efficiency']:.4f}",
        f"Initial residual field magnitude: {best_result['initial_field_mG']:.3f} mG",
        f"Final residual field magnitude: {best_result['final_field_mG']:.3f} mG",
        f"Time-averaged residual field magnitude: {best_result['mean_field_mG']:.3f} mG",
        f"Magnetic width used for PGC suppression: {best_result['magnetic_width_mG']:.3f} mG",
    ]
    path = output_dir / f"{prefix}_summary.txt"
    path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return path


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulate the effect of XYZ compensation coils on Rb87 optical molasses cooling."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional path to a JSON config file.",
    )
    parser.add_argument(
        "--write-default-config",
        type=Path,
        default=None,
        help="Write a default JSON config to the given path and exit.",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.write_default_config is not None:
        args.write_default_config.write_text(
            json.dumps(asdict(SimulationConfig()), indent=2),
            encoding="utf-8",
        )
        print(f"Default config written to: {args.write_default_config}")
        return

    config = load_config(args.config)
    output_dir = Path(__file__).resolve().parent / config.output.directory
    output_dir.mkdir(parents=True, exist_ok=True)

    scan_result = run_scan(config)
    csv_path = save_scan_csv(scan_result["records"], output_dir, config.output.prefix)
    overview_path = make_overview_figure(scan_result, output_dir, config.output.prefix)
    dynamics_path = make_dynamics_figure(config, scan_result["best_result"], output_dir, config.output.prefix)
    summary_path = write_summary(scan_result, output_dir, config.output.prefix)
    resolved_config_path = save_resolved_config(config, output_dir, config.output.prefix)

    best_result = scan_result["best_result"]
    best_x, best_y, best_z = best_result["setpoint_xyz"]
    print(f"Best compensation setpoint: X={best_x:.3f}, Y={best_y:.3f}, Z={best_z:.3f}")
    print(f"Final temperature: {best_result['final_temperature_uK']:.3f} uK")
    print(f"Cooling efficiency: {best_result['cooling_efficiency']:.4f}")
    print(f"Magnetic width: {best_result['magnetic_width_mG']:.3f} mG")
    print(f"Scan CSV: {csv_path}")
    print(f"Overview figure: {overview_path}")
    print(f"Dynamics figure: {dynamics_path}")
    print(f"Summary: {summary_path}")
    print(f"Resolved config: {resolved_config_path}")


if __name__ == "__main__":
    main()
