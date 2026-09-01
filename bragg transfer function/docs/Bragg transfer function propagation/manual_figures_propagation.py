"""Generate separate Model-A and Model-B figures for three propagation lengths."""

from __future__ import annotations

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
PROJECT_DIR = HERE.parents[1]
FIGURE_DIR = HERE / "figures"
FIGURE_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(PROJECT_DIR))

from bragg_transfer_function_propagation_ui import (  # noqa: E402
    PropagationParameters,
    _fringe_slope,
    _input_omega_from_width,
    _local_input_intensity,
    atom_phase_transfer_function,
    build_schedule,
    delay_phase_transfer,
    frequency_noise_transfer_function,
)


BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
SKY = "#56B4E9"
PURPLE = "#7B61A8"
GREY = "#606060"

DISTANCES = (0.0, 150.0, 2000.0)
DISTANCE_NAMES = {0.0: "Zero", 150.0: "OneFifty", 2000.0: "TwoThousand"}
DISTANCE_COLORS = {0.0: GREY, 150.0: BLUE, 2000.0: ORANGE}
HALF_WIDTH = 25.0e-6
PI_WIDTH = 50.0e-6
TARGET_HALF = 0.5 * np.pi
TARGET_PI = np.pi


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9.0,
            "axes.labelsize": 9.5,
            "axes.titlesize": 10.5,
            "legend.fontsize": 8.0,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.6,
            "savefig.bbox": "tight",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def parameters(distance_m: float, shape: str, model: str) -> PropagationParameters:
    return PropagationParameters(
        bragg_order=1,
        omega_pi_over_2=_input_omega_from_width(shape, HALF_WIDTH, TARGET_HALF),
        omega_pi=_input_omega_from_width(shape, PI_WIDTH, TARGET_PI),
        center_separation=0.250,
        distance_to_mirror=distance_m,
        pulse_shape=shape,
        model=model,
    )


PARAMS = {
    (shape, distance): parameters(distance, shape, "A: area compensated")
    for shape in ("Square", "Gaussian")
    for distance in DISTANCES
}
SCHEDULES = {key: build_schedule(value) for key, value in PARAMS.items()}
B_PARAMS = {
    (shape, distance): parameters(distance, shape, "B: fixed input")
    for shape in ("Square", "Gaussian")
    for distance in DISTANCES
}
B_SCHEDULES = {key: build_schedule(value) for key, value in B_PARAMS.items()}


def save_figure(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIGURE_DIR / f"{stem}.pdf")
    fig.savefig(FIGURE_DIR / f"{stem}.png", dpi=240, facecolor="white")
    plt.close(fig)


def pulse_panel(
    ax: plt.Axes,
    shape: str,
    distance: float,
    panel: str,
    params_map,
    schedules_map,
) -> None:
    params = params_map[(shape, distance)]
    pulse = schedules_map[(shape, distance)][0]
    span_us = 32.0 if shape == "Square" else 68.0
    local_us = np.linspace(-span_us, span_us + params.delay * 1.0e6, 1800)
    local_s = local_us * 1.0e-6
    forward, reflected = _local_input_intensity(local_s, pulse, params.delay)
    effective = pulse.omega(local_s) / pulse.input_omega
    ax.plot(local_us, forward, color=BLUE, label=r"forward $I(t)$")
    ax.plot(local_us, reflected, color=ORANGE, linestyle="--", label=r"reflected $I(t-\tau_d)$")
    ax.plot(local_us, effective, color=GREEN, linewidth=2.0, label=r"$\Omega_{\rm eff}/\Omega_{\rm in}$")
    ax.axvline(0.0, color=BLUE, linewidth=0.7, alpha=0.5)
    ax.axvline(params.delay * 1.0e6, color=ORANGE, linewidth=0.7, alpha=0.6)
    ax.set(
        xlabel=r"local time ($\mu$s)",
        ylabel="normalized amplitude",
        title=f"{panel}  {shape}, $L={distance:g}$ m",
    )
    ax.grid(alpha=0.22)
    if panel in {"a", "d"}:
        ax.legend(frameon=False, loc="upper right")


def figure_overlap_and_sensitivity(params_map, schedules_map, stem: str) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(11.2, 6.0), constrained_layout=True)
    panels = iter("abcdef")
    for row, shape in enumerate(("Square", "Gaussian")):
        for column, distance in enumerate(DISTANCES):
            pulse_panel(
                axes[row, column], shape, distance, next(panels), params_map, schedules_map
            )
    save_figure(fig, stem)


def local_rms(
    centre_frequencies: np.ndarray,
    params: PropagationParameters,
    schedule,
    offsets: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if offsets is None:
        unit_offsets = np.linspace(-1.0, 1.0, 13)
        half_span = np.minimum(2.0, 0.45 * centre_frequencies)
        sample_frequency = centre_frequencies[:, None] + half_span[:, None] * unit_offsets[None, :]
    else:
        sample_frequency = centre_frequencies[:, None] + offsets[None, :]
    response = atom_phase_transfer_function(sample_frequency.ravel(), params, schedule).reshape(sample_frequency.shape)
    rms = np.sqrt(np.mean(np.abs(response) ** 2, axis=1))
    return rms, sample_frequency, response


def atomic_rms_grid(
    centres: np.ndarray, params_map=PARAMS, schedules_map=SCHEDULES
) -> dict[tuple[str, float], np.ndarray]:
    return {
        key: local_rms(centres, params_map[key], schedules_map[key])[0]
        for key in params_map
    }


def figure_atomic_transfer(params_map, schedules_map, stem: str) -> None:
    low_frequency = np.linspace(0.0, 40.0, 2401)
    centres = np.geomspace(20.0, 1.0e5, 520)
    rms = atomic_rms_grid(centres, params_map, schedules_map)

    fig, axes = plt.subplots(2, 2, figsize=(10.4, 6.4), constrained_layout=True)
    ax = axes[0, 0]
    low_magnitudes = []
    for shape, linestyle, linewidth in (("Square", "-", 1.8), ("Gaussian", "--", 1.25)):
        for distance in DISTANCES:
            key = (shape, distance)
            response = atom_phase_transfer_function(
                low_frequency, params_map[key], schedules_map[key]
            )
            magnitude = np.abs(response)
            low_magnitudes.append(magnitude)
            ax.plot(
                low_frequency,
                magnitude,
                color=DISTANCE_COLORS[distance],
                linestyle=linestyle,
                linewidth=linewidth,
                label=f"{shape.lower()}, $L={distance:g}$ m",
            )
    ax.set(
        xlabel="frequency (Hz)",
        ylabel=r"phase-normalized $|H_{\rm AI}|$",
        title="a  Resolved low-frequency response",
    )
    ax.set_xlim(0.0, 40.0)
    ax.set_ylim(0.0, 1.06 * max(float(np.max(values)) for values in low_magnitudes))
    ax.grid(alpha=0.22)
    ax.legend(frameon=False, ncol=2, fontsize=7.1)

    ax = axes[0, 1]
    for distance in DISTANCES:
        ax.loglog(centres, rms[("Square", distance)], color=DISTANCE_COLORS[distance], linestyle={0.0: "-", 150.0: "--", 2000.0: ":"}[distance], label=f"$L={distance:g}$ m")
    ax.axvline(10.0e3, color=SKY, linewidth=1.0, linestyle="-.")
    ax.set(xlabel="frequency (Hz)", ylabel=r"local RMS of $|H_{\rm AI}|$", title="b  Square, phase-normalized envelope")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)
    if stem == "case_model_b_atomic_transfer":
        slope = _fringe_slope(schedules_map[("Square", 2000.0)])
        ax.text(
            0.04,
            0.92,
            rf"$L=2000$ m fringe slope $={slope:.4f}$",
            transform=ax.transAxes,
            va="top",
            fontsize=7.5,
            color=ORANGE,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 1.5},
        )

    ax = axes[1, 0]
    for distance in DISTANCES:
        ax.loglog(centres, rms[("Gaussian", distance)], color=DISTANCE_COLORS[distance], linestyle={0.0: "-", 150.0: "--", 2000.0: ":"}[distance], label=f"$L={distance:g}$ m")
    ax.axvline(10.0e3, color=SKY, linewidth=1.0, linestyle="-.", label="10 kHz")
    ax.set(xlabel="frequency (Hz)", ylabel=r"local RMS of $|H_{\rm AI}|$", title="c  Gaussian finite-pulse envelope")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)

    ax = axes[1, 1]
    square_zero = rms[("Square", 0.0)]
    gaussian_zero = rms[("Gaussian", 0.0)]
    square_ratios = {
        distance: rms[("Square", distance)] / square_zero
        for distance in (150.0, 2000.0)
    }
    gaussian_ratios = {
        distance: rms[("Gaussian", distance)] / gaussian_zero
        for distance in (150.0, 2000.0)
    }
    square_lines = [
        ax.semilogx(centres, square_ratios[150.0], color=BLUE, linestyle="--", label="square, 150 m")[0],
        ax.semilogx(centres, square_ratios[2000.0], color=ORANGE, label="square, 2000 m")[0],
    ]
    ax.axhline(1.0, color="black", linewidth=0.7)
    ax.set(xlabel="frequency (Hz)", title="d  Response ratio to $L=0$")
    ax.grid(which="both", alpha=0.22)
    if stem == "case_atomic_transfer":
        ax.set_ylabel("square: response ratio")
        gaussian_axis = ax.twinx()
        reliable = gaussian_zero >= 1.0e-3
        gaussian_lines = [
            gaussian_axis.semilogx(centres, np.where(reliable, 1.0e6 * (gaussian_ratios[150.0] - 1.0), np.nan), color=PURPLE, linestyle="-.", label="Gaussian, 150 m")[0],
            gaussian_axis.semilogx(centres, np.where(reliable, 1.0e6 * (gaussian_ratios[2000.0] - 1.0), np.nan), color=GREEN, linestyle=":", label="Gaussian, 2000 m")[0],
        ]
        gaussian_axis.set_ylabel("Gaussian: ratio minus 1 (ppm)")
        first_masked = int(np.flatnonzero(~reliable)[0])
        ax.axvspan(centres[first_masked], centres[-1], color=GREY, alpha=0.08)
        ax.legend(handles=square_lines + gaussian_lines, frameon=False, loc="upper left")
    else:
        gaussian_lines = [
            ax.semilogx(centres, gaussian_ratios[150.0], color=PURPLE, linestyle="-.", label="Gaussian, 150 m")[0],
            ax.semilogx(centres, gaussian_ratios[2000.0], color=GREEN, linestyle=":", label="Gaussian, 2000 m")[0],
        ]
        ax.set_yscale("log")
        ax.set_ylabel("response ratio")
        ax.legend(handles=square_lines + gaussian_lines, frameon=False)
    save_figure(fig, stem)


def combined_rms(
    centres: np.ndarray, shape: str, distance: float, params_map, schedules_map
):
    key = (shape, distance)
    _, frequency_samples, atom_samples = local_rms(
        centres, params_map[key], schedules_map[key]
    )
    delay_samples = delay_phase_transfer(frequency_samples, params_map[key].delay)
    source_samples = atom_samples * delay_samples
    frequency_samples_response = frequency_noise_transfer_function(frequency_samples, source_samples)
    source_rms = np.sqrt(np.mean(np.abs(source_samples) ** 2, axis=1))
    frequency_rms = np.sqrt(np.mean(np.abs(frequency_samples_response) ** 2, axis=1))
    return source_rms, frequency_rms


def figure_total_transfer(params_map, schedules_map, stem: str) -> None:
    centres = np.geomspace(0.1, 1.0e5, 620)
    combined = {
        (shape, distance): combined_rms(
            centres, shape, distance, params_map, schedules_map
        )
        for shape in ("Square", "Gaussian")
        for distance in (150.0, 2000.0)
    }

    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.35), constrained_layout=True)
    ax = axes[0]
    for distance in (150.0, 2000.0):
        delay = params_map[("Square", distance)].delay
        ax.loglog(centres, np.abs(delay_phase_transfer(centres, delay)), color=DISTANCE_COLORS[distance], label=f"$L={distance:g}$ m")
    ax.text(0.04, 0.08, r"$L=0$: $|D_d|=0$", transform=ax.transAxes, color=GREY)
    ax.set(xlabel="frequency (Hz)", ylabel=r"$|D_d|$", title="a  Propagation phase filter")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)

    ax = axes[1]
    for distance in (150.0, 2000.0):
        for shape, linestyle in (("Square", "-"), ("Gaussian", "--")):
            ax.loglog(centres, combined[(shape, distance)][0], color=DISTANCE_COLORS[distance], linestyle=linestyle, label=f"{shape.lower()}, {distance:g} m")
    ax.text(0.04, 0.08, r"$L=0$: $H_{\rm src\phi}=0$", transform=ax.transAxes, color=GREY)
    ax.set(xlabel="frequency (Hz)", ylabel=r"local RMS of $|H_{\rm src\phi}|$", title="b  Source-phase to atom-phase")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)

    ax = axes[2]
    for distance in (150.0, 2000.0):
        for shape, linestyle in (("Square", "-"), ("Gaussian", "--")):
            ax.loglog(centres, combined[(shape, distance)][1], color=DISTANCE_COLORS[distance], linestyle=linestyle, label=f"{shape.lower()}, {distance:g} m")
    ax.text(0.61, 0.08, r"$L=0$: $H_\nu=0$", transform=ax.transAxes, color=GREY)
    ax.set(xlabel="frequency (Hz)", ylabel=r"local RMS of $|H_\nu|$ (rad/Hz)", title="c  Frequency-noise to atom-phase")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)
    save_figure(fig, stem)


def rms_at(
    frequency_hz: float,
    shape: str,
    distance: float,
    params_map=PARAMS,
    schedules_map=SCHEDULES,
) -> float:
    offsets = np.linspace(-2.0, 2.0, 401)
    frequencies = np.maximum(frequency_hz + offsets, 1.0e-8)
    key = (shape, distance)
    response = atom_phase_transfer_function(
        frequencies, params_map[key], schedules_map[key]
    )
    return float(np.sqrt(np.mean(np.abs(response) ** 2)))


def macro(lines: list[str], name: str, value: float, fmt: str) -> None:
    lines.append(f"\\newcommand{{\\{name}}}{{{format(value, fmt)}}}")


def write_case_values() -> None:
    lines: list[str] = []
    gaussian_sigma_half = SCHEDULES[("Gaussian", 0.0)][0].width_parameter
    gaussian_sigma_pi = SCHEDULES[("Gaussian", 0.0)][1].width_parameter
    macro(lines, "CaseGaussHalfSigmaUs", gaussian_sigma_half * 1e6, ".6f")
    macro(lines, "CaseGaussPiSigmaUs", gaussian_sigma_pi * 1e6, ".6f")
    macro(lines, "CaseGaussInputPeak", SCHEDULES[("Gaussian", 0.0)][0].input_omega / (2 * np.pi * 1e3), ".4f")

    for distance in DISTANCES:
        suffix = DISTANCE_NAMES[distance]
        delay = PARAMS[("Square", distance)].delay
        square_half, square_pi = SCHEDULES[("Square", distance)][:2]
        gaussian_half, gaussian_pi = SCHEDULES[("Gaussian", distance)][:2]
        macro(lines, f"CaseDelay{suffix}Us", delay * 1e6, ".6f")
        if delay > 0.0:
            macro(lines, f"CaseFirstZero{suffix}KHz", 1.0 / delay / 1e3, ".3f")
        macro(lines, f"CaseSquareHalfOverlap{suffix}Us", square_half.duration * 1e6, ".6f")
        macro(lines, f"CaseSquarePiOverlap{suffix}Us", square_pi.duration * 1e6, ".6f")
        macro(lines, f"CaseSquareHalfScale{suffix}", square_half.area_scale, ".6f")
        macro(lines, f"CaseSquarePiScale{suffix}", square_pi.area_scale, ".6f")
        macro(lines, f"CaseSquareHalfPeak{suffix}", square_half.effective_peak_omega / (2 * np.pi * 1e3), ".4f")
        macro(lines, f"CaseSquarePiPeak{suffix}", square_pi.effective_peak_omega / (2 * np.pi * 1e3), ".4f")
        macro(lines, f"CaseGaussHalfSupport{suffix}Us", gaussian_half.duration * 1e6, ".6f")
        macro(lines, f"CaseGaussPiSupport{suffix}Us", gaussian_pi.duration * 1e6, ".6f")
        macro(lines, f"CaseGaussHalfRawRatio{suffix}", gaussian_half.raw_peak_omega / gaussian_half.input_omega, ".6f")
        macro(lines, f"CaseGaussPiRawRatio{suffix}", gaussian_pi.raw_peak_omega / gaussian_pi.input_omega, ".6f")
        macro(lines, f"CaseGaussHalfScale{suffix}", gaussian_half.area_scale, ".6f")
        macro(lines, f"CaseGaussPiScale{suffix}", gaussian_pi.area_scale, ".6f")
        macro(lines, f"CaseSquareTenK{suffix}", rms_at(1e4, "Square", distance), ".6f")
        macro(lines, f"CaseGaussTenK{suffix}", rms_at(1e4, "Gaussian", distance), ".6f")
        macro(lines, f"CaseSquareHundredK{suffix}", rms_at(1e5, "Square", distance), ".6e")
        macro(lines, f"CaseGaussHundredK{suffix}", rms_at(1e5, "Gaussian", distance), ".6e")
        if delay > 0.0:
            macro(lines, f"CaseDTenK{suffix}", abs(delay_phase_transfer(np.array([1e4]), delay)[0]), ".6f")
            macro(lines, f"CaseDHundredK{suffix}", abs(delay_phase_transfer(np.array([1e5]), delay)[0]), ".6f")

    for distance in DISTANCES:
        suffix = DISTANCE_NAMES[distance]
        square_half, square_pi = B_SCHEDULES[("Square", distance)][:2]
        gaussian_half, gaussian_pi = B_SCHEDULES[("Gaussian", distance)][:2]
        macro(lines, f"CaseBSquareHalfAreaRatio{suffix}", square_half.effective_area / TARGET_HALF, ".6f")
        macro(lines, f"CaseBSquarePiAreaRatio{suffix}", square_pi.effective_area / TARGET_PI, ".6f")
        macro(lines, f"CaseBGaussHalfAreaRatio{suffix}", gaussian_half.effective_area / TARGET_HALF, ".6f")
        macro(lines, f"CaseBGaussPiAreaRatio{suffix}", gaussian_pi.effective_area / TARGET_PI, ".6f")
        macro(lines, f"CaseBSquareHalfAreaPi{suffix}", square_half.effective_area / np.pi, ".6f")
        macro(lines, f"CaseBSquarePiAreaPi{suffix}", square_pi.effective_area / np.pi, ".6f")
        macro(lines, f"CaseBGaussHalfAreaPi{suffix}", gaussian_half.effective_area / np.pi, ".6f")
        macro(lines, f"CaseBGaussPiAreaPi{suffix}", gaussian_pi.effective_area / np.pi, ".6f")
        macro(lines, f"CaseBSquareSlope{suffix}", _fringe_slope(B_SCHEDULES[("Square", distance)]), ".6f")
        macro(lines, f"CaseBGaussSlope{suffix}", _fringe_slope(B_SCHEDULES[("Gaussian", distance)]), ".6f")
        macro(lines, f"CaseBSquareTenK{suffix}", rms_at(1e4, "Square", distance, B_PARAMS, B_SCHEDULES), ".6f")
        macro(lines, f"CaseBGaussTenK{suffix}", rms_at(1e4, "Gaussian", distance, B_PARAMS, B_SCHEDULES), ".6f")
        macro(lines, f"CaseBSquareHundredK{suffix}", rms_at(1e5, "Square", distance, B_PARAMS, B_SCHEDULES), ".6e")
        macro(lines, f"CaseBGaussHundredK{suffix}", rms_at(1e5, "Gaussian", distance, B_PARAMS, B_SCHEDULES), ".6e")
    (HERE / "case_values.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    configure_style()
    figure_overlap_and_sensitivity(PARAMS, SCHEDULES, "case_overlap_sensitivity")
    figure_atomic_transfer(PARAMS, SCHEDULES, "case_atomic_transfer")
    figure_total_transfer(PARAMS, SCHEDULES, "case_total_transfer")
    figure_overlap_and_sensitivity(
        B_PARAMS, B_SCHEDULES, "case_model_b_overlap_sensitivity"
    )
    figure_atomic_transfer(
        B_PARAMS, B_SCHEDULES, "case_model_b_atomic_transfer"
    )
    figure_total_transfer(
        B_PARAMS, B_SCHEDULES, "case_model_b_total_transfer"
    )
    write_case_values()
    print(f"Wrote separate Model-A and Model-B figures for L = 0, 150 and 2000 m to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
