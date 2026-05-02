from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


AMU_KG = 1.66053906660e-27
PLANCK_J_S = 6.62607015e-34
BOHR_MAGNETON_J_T = 9.2740100783e-24
MU0_T_M_PER_A = 4.0e-7 * np.pi
TESLA_TO_MG = 1.0e7
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
    zero_field_temperature_uK: float = 2.0
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
    static_stray_field_mG: tuple[float, float, float] = (0, -120, 0)
    mot_switch_off_field_mG: tuple[float, float, float] = (0, 10000, 10000)
    mot_decay_tau_ms: float = 0.5


@dataclass(frozen=True)
class CoilGeometryConfig:
    turns_per_coil: int = 15
    side_length_cm: float = 30.0
    center_to_coil_cm: float = 20.0


@dataclass(frozen=True)
class AxisScan:
    start: float
    stop: float
    points: int

    def values(self) -> np.ndarray:
        return np.linspace(self.start, self.stop, self.points)


@dataclass(frozen=True)
class CurrentScanConfig:
    x_current_A: AxisScan = field(default_factory=lambda: AxisScan(-1.0, 1.0, 25))
    y_current_A: AxisScan = field(default_factory=lambda: AxisScan(-1.0, 1.0, 25))
    z_current_A: AxisScan = field(default_factory=lambda: AxisScan(-1.0, 1.0, 25))


@dataclass(frozen=True)
class RefinementConfig:
    enabled: bool = True
    steps: int = 1
    points_per_axis: int = 15
    target_step_A: float = 0.01


@dataclass(frozen=True)
class OutputConfig:
    directory: str = "outputs"
    prefix: str = "rb87_pgc_current_scan"


@dataclass(frozen=True)
class SimulationConfig:
    atom: AtomConfig = field(default_factory=AtomConfig)
    molasses: MolassesConfig = field(default_factory=MolassesConfig)
    fields: FieldConfig = field(default_factory=FieldConfig)
    coil_geometry: CoilGeometryConfig = field(default_factory=CoilGeometryConfig)
    scan: CurrentScanConfig = field(default_factory=CurrentScanConfig)
    refinement: RefinementConfig = field(default_factory=RefinementConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    @classmethod
    def from_dict(cls, data: dict) -> "SimulationConfig":
        field_block = data.get("fields", {})
        scan_block = data.get("scan", {})
        return cls(
            atom=AtomConfig(**data.get("atom", {})),
            molasses=MolassesConfig(**data.get("molasses", {})),
            fields=FieldConfig(
                static_stray_field_mG=tuple(
                    field_block.get("static_stray_field_mG", FieldConfig.static_stray_field_mG)
                ),
                mot_switch_off_field_mG=tuple(
                    field_block.get("mot_switch_off_field_mG", FieldConfig.mot_switch_off_field_mG)
                ),
                mot_decay_tau_ms=field_block.get("mot_decay_tau_ms", FieldConfig.mot_decay_tau_ms),
            ),
            coil_geometry=CoilGeometryConfig(**data.get("coil_geometry", {})),
            scan=CurrentScanConfig(
                x_current_A=AxisScan(**scan_block.get("x_current_A", asdict(CurrentScanConfig().x_current_A))),
                y_current_A=AxisScan(**scan_block.get("y_current_A", asdict(CurrentScanConfig().y_current_A))),
                z_current_A=AxisScan(**scan_block.get("z_current_A", asdict(CurrentScanConfig().z_current_A))),
            ),
            refinement=RefinementConfig(**data.get("refinement", {})),
            output=OutputConfig(**data.get("output", {})),
        )


def load_config(path: Path | None) -> SimulationConfig:
    if path is None:
        return SimulationConfig()
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return SimulationConfig.from_dict(data)


def square_pair_center_field_mG_per_A(geometry: CoilGeometryConfig) -> float:
    half_side_m = 0.5 * geometry.side_length_cm * 1.0e-2
    center_to_coil_m = geometry.center_to_coil_cm * 1.0e-2

    numerator = 4.0 * MU0_T_M_PER_A * geometry.turns_per_coil * half_side_m**2
    denominator = np.pi * (half_side_m**2 + center_to_coil_m**2) * np.sqrt(
        2.0 * half_side_m**2 + center_to_coil_m**2
    )
    return TESLA_TO_MG * numerator / denominator


def coil_field_matrix_mG_per_A(config: SimulationConfig) -> np.ndarray:
    coefficient = square_pair_center_field_mG_per_A(config.coil_geometry)
    return np.diag([coefficient, coefficient, coefficient])


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


def coil_field_from_currents_mG(config: SimulationConfig, current_xyz_A: np.ndarray) -> np.ndarray:
    return coil_field_matrix_mG_per_A(config) @ current_xyz_A


def residual_field_trace_mG(
    config: SimulationConfig,
    current_xyz_A: np.ndarray,
    time_ms: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    static_field = np.asarray(config.fields.static_stray_field_mG, dtype=float)
    decay_field = np.asarray(config.fields.mot_switch_off_field_mG, dtype=float)
    coil_field = coil_field_from_currents_mG(config, current_xyz_A)

    if config.fields.mot_decay_tau_ms > 0.0:
        decay_scale = np.exp(-time_ms / config.fields.mot_decay_tau_ms)
    else:
        decay_scale = np.zeros_like(time_ms)

    total_field = static_field + coil_field + decay_scale[:, None] * decay_field
    return total_field, coil_field


def simulate_one_setting(config: SimulationConfig, current_xyz_A: np.ndarray) -> dict:
    time_ms = time_axis_ms(config)
    dt_ms = np.diff(time_ms)
    field_trace, coil_field = residual_field_trace_mG(config, current_xyz_A, time_ms)
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
        "current_xyz_A": current_xyz_A.copy(),
        "coil_field_mG": coil_field,
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


def evaluate_current_grid(
    config: SimulationConfig,
    x_currents: np.ndarray,
    y_currents: np.ndarray,
    z_currents: np.ndarray,
) -> dict:
    temp_grid = np.empty((len(z_currents), len(y_currents), len(x_currents)))
    efficiency_grid = np.empty_like(temp_grid)
    mean_field_grid = np.empty_like(temp_grid)
    records: list[dict] = []

    best_result = None
    best_indices = None

    for iz, z_current in enumerate(z_currents):
        for iy, y_current in enumerate(y_currents):
            for ix, x_current in enumerate(x_currents):
                currents = np.array([x_current, y_current, z_current], dtype=float)
                result = simulate_one_setting(config, currents)
                coil_field = result["coil_field_mG"]

                temp_grid[iz, iy, ix] = result["final_temperature_uK"]
                efficiency_grid[iz, iy, ix] = result["cooling_efficiency"]
                mean_field_grid[iz, iy, ix] = result["mean_field_mG"]

                record = {
                    "current_x_A": float(x_current),
                    "current_y_A": float(y_current),
                    "current_z_A": float(z_current),
                    "coil_field_x_mG": float(coil_field[0]),
                    "coil_field_y_mG": float(coil_field[1]),
                    "coil_field_z_mG": float(coil_field[2]),
                    "coil_field_norm_mG": float(np.linalg.norm(coil_field)),
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
        "x_currents": x_currents,
        "y_currents": y_currents,
        "z_currents": z_currents,
        "temp_grid": temp_grid,
        "efficiency_grid": efficiency_grid,
        "mean_field_grid": mean_field_grid,
        "records": records,
        "best_result": best_result,
        "best_indices": best_indices,
    }


def run_scan(config: SimulationConfig) -> dict:
    return evaluate_current_grid(
        config,
        config.scan.x_current_A.values(),
        config.scan.y_current_A.values(),
        config.scan.z_current_A.values(),
    )


def axis_step(values: np.ndarray) -> float:
    if len(values) < 2:
        return 0.0
    return float(abs(values[1] - values[0]))


def local_axis_values(center: float, half_range: float, points: int, lower: float, upper: float) -> np.ndarray:
    center = float(np.clip(center, lower, upper))
    if points <= 1 or half_range <= 0.0:
        return np.array([center], dtype=float)
    start = max(lower, center - half_range)
    stop = min(upper, center + half_range)
    if stop <= start:
        return np.array([center], dtype=float)
    return np.linspace(start, stop, points)


def refinement_points_for_half_range(half_range: float, minimum_points: int, target_step_A: float) -> int:
    points = max(int(minimum_points), 2)
    if target_step_A <= 0.0 or half_range <= 0.0:
        return points
    required_points = int(np.ceil((2.0 * half_range) / target_step_A)) + 1
    return max(points, required_points)


def refine_best_current(config: SimulationConfig, coarse_result: dict) -> dict | None:
    if not config.refinement.enabled:
        return None

    x_half_range = axis_step(coarse_result["x_currents"])
    y_half_range = axis_step(coarse_result["y_currents"])
    z_half_range = axis_step(coarse_result["z_currents"])
    if max(x_half_range, y_half_range, z_half_range) <= 0.0:
        return None

    center = coarse_result["best_result"]["current_xyz_A"].copy()
    all_records: list[dict] = []
    stage_summaries: list[dict] = []
    latest_grid = None

    for stage in range(1, config.refinement.steps + 1):
        x_points = refinement_points_for_half_range(
            x_half_range,
            config.refinement.points_per_axis,
            config.refinement.target_step_A,
        )
        y_points = refinement_points_for_half_range(
            y_half_range,
            config.refinement.points_per_axis,
            config.refinement.target_step_A,
        )
        z_points = refinement_points_for_half_range(
            z_half_range,
            config.refinement.points_per_axis,
            config.refinement.target_step_A,
        )

        x_currents = local_axis_values(
            center[0],
            x_half_range,
            x_points,
            config.scan.x_current_A.start,
            config.scan.x_current_A.stop,
        )
        y_currents = local_axis_values(
            center[1],
            y_half_range,
            y_points,
            config.scan.y_current_A.start,
            config.scan.y_current_A.stop,
        )
        z_currents = local_axis_values(
            center[2],
            z_half_range,
            z_points,
            config.scan.z_current_A.start,
            config.scan.z_current_A.stop,
        )

        latest_grid = evaluate_current_grid(config, x_currents, y_currents, z_currents)
        center = latest_grid["best_result"]["current_xyz_A"].copy()

        for record in latest_grid["records"]:
            record["refinement_stage"] = stage
            all_records.append(record)

        stage_summaries.append(
            {
                "stage": stage,
                "x_range_A": [float(x_currents[0]), float(x_currents[-1])],
                "y_range_A": [float(y_currents[0]), float(y_currents[-1])],
                "z_range_A": [float(z_currents[0]), float(z_currents[-1])],
                "best_current_xyz_A": center.tolist(),
                "best_temperature_uK": float(latest_grid["best_result"]["final_temperature_uK"]),
            }
        )

        x_step = axis_step(x_currents)
        y_step = axis_step(y_currents)
        z_step = axis_step(z_currents)
        if max(x_step, y_step, z_step) <= 0.0:
            break
        if max(x_step, y_step, z_step) <= config.refinement.target_step_A + 1.0e-12:
            break
        x_half_range = x_step
        y_half_range = y_step
        z_half_range = z_step

    if latest_grid is None:
        return None

    return {
        "best_result": latest_grid["best_result"],
        "records": all_records,
        "stage_summaries": stage_summaries,
        "final_grid": latest_grid,
    }


def save_scan_csv(records: list[dict], output_dir: Path, prefix: str) -> Path:
    path = output_dir / f"{prefix}_scan.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
    return path


def save_resolved_config(config: SimulationConfig, output_dir: Path, prefix: str) -> Path:
    resolved = asdict(config)
    resolved["derived_coil_field_matrix_mG_per_A"] = coil_field_matrix_mG_per_A(config).tolist()
    resolved["derived_center_field_per_axis_mG_per_A"] = square_pair_center_field_mG_per_A(
        config.coil_geometry
    )

    path = output_dir / f"{prefix}_resolved_config.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(resolved, handle, indent=2)
    return path


def set_axes_image(ax, image, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.figure.colorbar(image, ax=ax, shrink=0.85)


def choose_overview_plot_result(coarse_result: dict, refinement_result: dict | None) -> tuple[dict, str]:
    plot_result = coarse_result
    plot_label = "coarse grid"
    if refinement_result is not None and refinement_result.get("final_grid") is not None:
        plot_result = refinement_result["final_grid"]
        plot_label = "refined grid"
    return plot_result, plot_label


def plot_overview_on_axes(
    config: SimulationConfig,
    coarse_result: dict,
    best_result: dict,
    refinement_result: dict | None,
    axes,
) -> dict:
    plot_result, plot_label = choose_overview_plot_result(coarse_result, refinement_result)

    x_currents = plot_result["x_currents"]
    y_currents = plot_result["y_currents"]
    z_currents = plot_result["z_currents"]
    temp_grid = plot_result["temp_grid"]
    best_iz, best_iy, best_ix = plot_result["best_indices"]
    field_per_amp = square_pair_center_field_mG_per_A(config.coil_geometry)
    x_step = axis_step(x_currents)
    y_step = axis_step(y_currents)
    z_step = axis_step(z_currents)

    xy_temp = temp_grid[best_iz, :, :]
    xz_temp = temp_grid[:, best_iy, :]
    yz_temp = temp_grid[:, :, best_ix]

    im_xy = axes[0, 0].imshow(
        xy_temp,
        origin="lower",
        aspect="auto",
        extent=[x_currents[0], x_currents[-1], y_currents[0], y_currents[-1]],
        cmap="viridis_r",
    )
    axes[0, 0].plot(best_result["current_xyz_A"][0], best_result["current_xyz_A"][1], "ro")
    set_axes_image(
        axes[0, 0],
        im_xy,
        f"Final temperature in XY plane ({plot_label}, Iz = {z_currents[best_iz]:.3f} A)",
        "Current X (A)",
        "Current Y (A)",
    )

    im_xz = axes[0, 1].imshow(
        xz_temp,
        origin="lower",
        aspect="auto",
        extent=[x_currents[0], x_currents[-1], z_currents[0], z_currents[-1]],
        cmap="viridis_r",
    )
    axes[0, 1].plot(best_result["current_xyz_A"][0], best_result["current_xyz_A"][2], "ro")
    set_axes_image(
        axes[0, 1],
        im_xz,
        f"Final temperature in XZ plane ({plot_label}, Iy = {y_currents[best_iy]:.3f} A)",
        "Current X (A)",
        "Current Z (A)",
    )

    im_yz = axes[1, 0].imshow(
        yz_temp,
        origin="lower",
        aspect="auto",
        extent=[y_currents[0], y_currents[-1], z_currents[0], z_currents[-1]],
        cmap="viridis_r",
    )
    axes[1, 0].plot(best_result["current_xyz_A"][1], best_result["current_xyz_A"][2], "ro")
    set_axes_image(
        axes[1, 0],
        im_yz,
        f"Final temperature in YZ plane ({plot_label}, Ix = {x_currents[best_ix]:.3f} A)",
        "Current Y (A)",
        "Current Z (A)",
    )

    axes[1, 1].plot(x_currents, temp_grid[best_iz, best_iy, :], label="Scan X")
    axes[1, 1].plot(y_currents, temp_grid[best_iz, :, best_ix], label="Scan Y")
    axes[1, 1].plot(z_currents, temp_grid[:, best_iy, best_ix], label="Scan Z")
    axes[1, 1].axhline(best_result["final_temperature_uK"], color="k", linestyle="--", linewidth=1)
    axes[1, 1].set_title("1D cuts through the best point")
    axes[1, 1].set_xlabel("Current (A)")
    axes[1, 1].set_ylabel("Final temperature (uK)")
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].legend()
    axes[1, 1].text(
        0.03,
        0.05,
        (
            f"Center field conversion:\n1 A -> {field_per_amp:.2f} mG\n"
            f"Overview grid step:\n"
            f"dIx={x_step:.4f} A, dIy={y_step:.4f} A, dIz={z_step:.4f} A\n"
            f"Final best current:\n"
            f"({best_result['current_xyz_A'][0]:.3f}, {best_result['current_xyz_A'][1]:.3f}, "
            f"{best_result['current_xyz_A'][2]:.3f}) A"
        ),
        transform=axes[1, 1].transAxes,
        va="bottom",
        ha="left",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85},
    )

    return {
        "plot_result": plot_result,
        "plot_label": plot_label,
        "grid_steps_A": {"x": x_step, "y": y_step, "z": z_step},
    }


def plot_dynamics_on_axes(config: SimulationConfig, best_result: dict, axes) -> dict:
    zero_current_result = simulate_one_setting(config, np.zeros(3, dtype=float))
    field_per_amp = square_pair_center_field_mG_per_A(config.coil_geometry)

    time_ms = best_result["time_ms"]
    best_trace = best_result["field_trace_mG"]
    axes[0, 0].plot(time_ms, best_trace[:, 0], label="Bx")
    axes[0, 0].plot(time_ms, best_trace[:, 1], label="By")
    axes[0, 0].plot(time_ms, best_trace[:, 2], label="Bz")
    axes[0, 0].set_title("Residual field components at best current setpoint")
    axes[0, 0].set_xlabel("Time after MOT switch-off (ms)")
    axes[0, 0].set_ylabel("Field (mG)")
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].legend()

    axes[0, 1].plot(zero_current_result["time_ms"], zero_current_result["field_norm_mG"], label="Zero current")
    axes[0, 1].plot(best_result["time_ms"], best_result["field_norm_mG"], label="Best current")
    axes[0, 1].axhline(best_result["magnetic_width_mG"], color="k", linestyle="--", linewidth=1, label="PGC width")
    axes[0, 1].set_title("Residual field magnitude")
    axes[0, 1].set_xlabel("Time after MOT switch-off (ms)")
    axes[0, 1].set_ylabel("|B| (mG)")
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].legend()

    axes[1, 0].plot(
        zero_current_result["time_ms"],
        zero_current_result["relative_efficiency_trace"],
        label="Zero current",
    )
    axes[1, 0].plot(best_result["time_ms"], best_result["relative_efficiency_trace"], label="Best current")
    axes[1, 0].set_title("Instantaneous relative cooling efficiency")
    axes[1, 0].set_xlabel("Time after MOT switch-off (ms)")
    axes[1, 0].set_ylabel("Relative efficiency")
    axes[1, 0].set_ylim(0.0, 1.05)
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].legend()

    axes[1, 1].plot(zero_current_result["time_ms"], zero_current_result["temperature_uK"], label="Zero current")
    axes[1, 1].plot(best_result["time_ms"], best_result["temperature_uK"], label="Best current")
    axes[1, 1].set_title("Temperature evolution during optical molasses")
    axes[1, 1].set_xlabel("Time after MOT switch-off (ms)")
    axes[1, 1].set_ylabel("Temperature (uK)")
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].legend()
    axes[1, 1].text(
        0.03,
        0.95,
        (
            f"Best current: ({best_result['current_xyz_A'][0]:.3f}, "
            f"{best_result['current_xyz_A'][1]:.3f}, {best_result['current_xyz_A'][2]:.3f}) A\n"
            f"Field coefficient: {field_per_amp:.2f} mG/A"
        ),
        transform=axes[1, 1].transAxes,
        va="top",
        ha="left",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85},
    )

    return {"zero_current_result": zero_current_result}


def make_overview_figure(
    config: SimulationConfig,
    coarse_result: dict,
    best_result: dict,
    refinement_result: dict | None,
    output_dir: Path,
    prefix: str,
) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), constrained_layout=True)
    plot_overview_on_axes(config, coarse_result, best_result, refinement_result, axes)
    path = output_dir / f"{prefix}_overview.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def make_dynamics_figure(config: SimulationConfig, best_result: dict, output_dir: Path, prefix: str) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
    plot_dynamics_on_axes(config, best_result, axes)
    path = output_dir / f"{prefix}_dynamics.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def write_summary(
    config: SimulationConfig,
    coarse_result: dict,
    best_result: dict,
    refinement_result: dict | None,
    output_dir: Path,
    prefix: str,
) -> Path:
    coarse_best = coarse_result["best_result"]
    best_ix, best_iy, best_iz = best_result["current_xyz_A"]
    coil_bx, coil_by, coil_bz = best_result["coil_field_mG"]
    field_per_amp = square_pair_center_field_mG_per_A(config.coil_geometry)

    summary_lines = [
        "Rb87 optical molasses current-scan simulation summary",
        f"Center-field conversion for each axis pair: 1 A -> {field_per_amp:.6f} mG",
        (
            "Coarse-grid best current setpoint: "
            f"Ix={coarse_best['current_xyz_A'][0]:.6f} A, "
            f"Iy={coarse_best['current_xyz_A'][1]:.6f} A, "
            f"Iz={coarse_best['current_xyz_A'][2]:.6f} A"
        ),
        f"Final best current setpoint: Ix={best_ix:.6f} A, Iy={best_iy:.6f} A, Iz={best_iz:.6f} A",
        f"Compensation field at best setpoint: Bx={coil_bx:.6f} mG, By={coil_by:.6f} mG, Bz={coil_bz:.6f} mG",
        f"Predicted final temperature: {best_result['final_temperature_uK']:.6f} uK",
        f"Cooling efficiency (0=no cooling, 1=zero-field limit): {best_result['cooling_efficiency']:.6f}",
        f"Initial residual field magnitude: {best_result['initial_field_mG']:.6f} mG",
        f"Final residual field magnitude: {best_result['final_field_mG']:.6f} mG",
        f"Time-averaged residual field magnitude: {best_result['mean_field_mG']:.6f} mG",
        f"Magnetic width used for PGC suppression: {best_result['magnetic_width_mG']:.6f} mG",
        "",
        "Geometry used:",
        f"  turns per coil = {config.coil_geometry.turns_per_coil}",
        f"  square side length = {config.coil_geometry.side_length_cm:.6f} cm",
        f"  center to each coil = {config.coil_geometry.center_to_coil_cm:.6f} cm",
    ]
    if refinement_result is not None:
        summary_lines.extend(["", "Local refinement stages:"])
        for stage in refinement_result["stage_summaries"]:
            summary_lines.append(
                (
                    f"  stage {stage['stage']}: "
                    f"x in [{stage['x_range_A'][0]:.6f}, {stage['x_range_A'][1]:.6f}] A, "
                    f"y in [{stage['y_range_A'][0]:.6f}, {stage['y_range_A'][1]:.6f}] A, "
                    f"z in [{stage['z_range_A'][0]:.6f}, {stage['z_range_A'][1]:.6f}] A, "
                    f"best = ({stage['best_current_xyz_A'][0]:.6f}, "
                    f"{stage['best_current_xyz_A'][1]:.6f}, "
                    f"{stage['best_current_xyz_A'][2]:.6f}) A, "
                    f"T = {stage['best_temperature_uK']:.6f} uK"
                )
            )
        final_grid = refinement_result.get("final_grid")
        if final_grid is not None:
            summary_lines.extend(
                [
                    "",
                    "Overview figure uses the final refined grid:",
                    (
                        f"  dIx = {axis_step(final_grid['x_currents']):.6f} A, "
                        f"dIy = {axis_step(final_grid['y_currents']):.6f} A, "
                        f"dIz = {axis_step(final_grid['z_currents']):.6f} A"
                    ),
                ]
            )
    path = output_dir / f"{prefix}_summary.txt"
    path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return path


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulate XYZ compensation-coil current scans for Rb87 optical molasses."
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

    coarse_result = run_scan(config)
    refinement_result = refine_best_current(config, coarse_result)
    best_result = coarse_result["best_result"] if refinement_result is None else refinement_result["best_result"]

    csv_path = save_scan_csv(coarse_result["records"], output_dir, config.output.prefix)
    refined_csv_path = None
    if refinement_result is not None and refinement_result["records"]:
        refined_csv_path = save_scan_csv(
            refinement_result["records"],
            output_dir,
            f"{config.output.prefix}_refined",
        )
    overview_path = make_overview_figure(
        config,
        coarse_result,
        best_result,
        refinement_result,
        output_dir,
        config.output.prefix,
    )
    dynamics_path = make_dynamics_figure(config, best_result, output_dir, config.output.prefix)
    summary_path = write_summary(
        config,
        coarse_result,
        best_result,
        refinement_result,
        output_dir,
        config.output.prefix,
    )
    resolved_config_path = save_resolved_config(config, output_dir, config.output.prefix)

    field_per_amp = square_pair_center_field_mG_per_A(config.coil_geometry)
    current_x, current_y, current_z = best_result["current_xyz_A"]
    field_x, field_y, field_z = best_result["coil_field_mG"]

    print(f"Center field conversion: 1 A -> {field_per_amp:.6f} mG")
    print(
        "Coarse-grid best current: "
        f"Ix={coarse_result['best_result']['current_xyz_A'][0]:.6f} A, "
        f"Iy={coarse_result['best_result']['current_xyz_A'][1]:.6f} A, "
        f"Iz={coarse_result['best_result']['current_xyz_A'][2]:.6f} A"
    )
    print(f"Best current setpoint: Ix={current_x:.6f} A, Iy={current_y:.6f} A, Iz={current_z:.6f} A")
    print(f"Compensation field: Bx={field_x:.6f} mG, By={field_y:.6f} mG, Bz={field_z:.6f} mG")
    print(f"Final temperature: {best_result['final_temperature_uK']:.6f} uK")
    print(f"Cooling efficiency: {best_result['cooling_efficiency']:.6f}")
    print(f"Magnetic width: {best_result['magnetic_width_mG']:.6f} mG")
    print(f"Scan CSV: {csv_path}")
    if refined_csv_path is not None:
        print(f"Refined scan CSV: {refined_csv_path}")
    print(f"Overview figure: {overview_path}")
    print(f"Dynamics figure: {dynamics_path}")
    print(f"Summary: {summary_path}")
    print(f"Resolved config: {resolved_config_path}")


if __name__ == "__main__":
    main()
