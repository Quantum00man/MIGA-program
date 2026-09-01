"""Generate reproducible Model-A figures for the propagation-aware manual."""

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
    _input_omega_from_width,
    _local_input_intensity,
    atom_phase_transfer_function,
    build_schedule,
    delay_phase_transfer,
    frequency_noise_transfer_function,
    sensitivity_function,
)


BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
SKY = "#56B4E9"
PURPLE = "#7B61A8"
GREY = "#606060"

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


def parameters(distance_m: float, shape: str) -> PropagationParameters:
    return PropagationParameters(
        bragg_order=1,
        omega_pi_over_2=_input_omega_from_width(
            shape, HALF_WIDTH, TARGET_HALF
        ),
        omega_pi=_input_omega_from_width(shape, PI_WIDTH, TARGET_PI),
        center_separation=0.250,
        distance_to_mirror=distance_m,
        pulse_shape=shape,
        model="A: area compensated",
    )


P_SQUARE_0 = parameters(0.0, "Square")
P_SQUARE_L = parameters(150.0, "Square")
P_GAUSS_0 = parameters(0.0, "Gaussian")
P_GAUSS_L = parameters(150.0, "Gaussian")
S_SQUARE_0 = build_schedule(P_SQUARE_0)
S_SQUARE_L = build_schedule(P_SQUARE_L)
S_GAUSS_0 = build_schedule(P_GAUSS_0)
S_GAUSS_L = build_schedule(P_GAUSS_L)


def save_figure(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIGURE_DIR / f"{stem}.pdf")
    fig.savefig(FIGURE_DIR / f"{stem}.png", dpi=240, facecolor="white")
    plt.close(fig)


def pulse_panel(ax: plt.Axes, params, schedule, span_us: float, title: str) -> None:
    pulse = schedule[0]
    local_us = np.linspace(-span_us, span_us + params.delay * 1.0e6, 1800)
    local_s = local_us * 1.0e-6
    forward, reflected = _local_input_intensity(local_s, pulse, params.delay)
    effective = pulse.omega(local_s) / pulse.input_omega
    ax.plot(local_us, forward, color=BLUE, label=r"forward $I(t)$")
    ax.plot(
        local_us,
        reflected,
        color=ORANGE,
        linestyle="--",
        label=r"reflected $I(t-\tau_d)$",
    )
    ax.plot(
        local_us,
        effective,
        color=GREEN,
        linewidth=2.0,
        label=r"compensated $\Omega_{\rm eff}/\Omega_{\rm in}$",
    )
    ax.axvline(0.0, color=BLUE, linewidth=0.7, alpha=0.5)
    ax.axvline(params.delay * 1.0e6, color=ORANGE, linewidth=0.7, alpha=0.6)
    ax.set(
        xlabel=r"time relative to command centre ($\mu$s)",
        ylabel="normalized amplitude",
        title=title,
    )
    ax.grid(alpha=0.22)
    ax.legend(frameon=False, loc="upper right")


def sequence_time(schedule) -> np.ndarray:
    return np.concatenate(
        [
            np.linspace(schedule[0].start, schedule[0].end, 320, endpoint=False),
            np.linspace(schedule[0].end, schedule[1].start, 180, endpoint=False),
            np.linspace(schedule[1].start, schedule[1].end, 420, endpoint=False),
            np.linspace(schedule[1].end, schedule[2].start, 180, endpoint=False),
            np.linspace(schedule[2].start, schedule[2].end, 320),
        ]
    )


def sensitivity_panel(ax: plt.Axes, params, schedule, title: str) -> None:
    time = sequence_time(schedule)
    response = sensitivity_function(time, params, schedule)
    ax.plot(time * 1.0e3, response, color=GREEN)
    for pulse in schedule:
        ax.axvspan(
            pulse.start * 1.0e3,
            pulse.end * 1.0e3,
            color=SKY,
            alpha=0.12,
        )
    ax.axhline(0.0, color="black", linewidth=0.7)
    ax.set(xlabel="time (ms)", ylabel=r"$s(t)$", title=title)
    ax.set_ylim(-1.13, 1.13)
    ax.grid(alpha=0.22)


def figure_overlap_and_sensitivity() -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10.4, 6.4), constrained_layout=True)
    pulse_panel(
        axes[0, 0], P_SQUARE_L, S_SQUARE_L, 30.0, r"a  Square $\pi/2$ overlap"
    )
    pulse_panel(
        axes[0, 1], P_GAUSS_L, S_GAUSS_L, 65.0, r"b  Gaussian $\pi/2$ overlap"
    )
    sensitivity_panel(
        axes[1, 0], P_SQUARE_L, S_SQUARE_L, "c  Square sensitivity function"
    )
    sensitivity_panel(
        axes[1, 1], P_GAUSS_L, S_GAUSS_L, "d  Gaussian sensitivity function"
    )
    save_figure(fig, "case_overlap_sensitivity")


def local_rms(
    centre_frequencies: np.ndarray,
    params: PropagationParameters,
    schedule,
    offsets: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if offsets is None:
        unit_offsets = np.linspace(-1.0, 1.0, 13)
        half_span = np.minimum(2.0, 0.45 * centre_frequencies)
        sample_frequency = (
            centre_frequencies[:, None]
            + half_span[:, None] * unit_offsets[None, :]
        )
    else:
        sample_frequency = centre_frequencies[:, None] + offsets[None, :]
    response = atom_phase_transfer_function(
        sample_frequency.ravel(), params, schedule
    ).reshape(sample_frequency.shape)
    rms = np.sqrt(np.mean(np.abs(response) ** 2, axis=1))
    return rms, sample_frequency, response


def figure_atomic_transfer() -> None:
    low_frequency = np.linspace(0.0, 40.0, 2401)
    hs0_low = atom_phase_transfer_function(low_frequency, P_SQUARE_0, S_SQUARE_0)
    hsl_low = atom_phase_transfer_function(low_frequency, P_SQUARE_L, S_SQUARE_L)
    hgl_low = atom_phase_transfer_function(low_frequency, P_GAUSS_L, S_GAUSS_L)

    centres = np.geomspace(20.0, 1.0e5, 520)
    hs0, _, _ = local_rms(centres, P_SQUARE_0, S_SQUARE_0)
    hsl, _, _ = local_rms(centres, P_SQUARE_L, S_SQUARE_L)
    hg0, _, _ = local_rms(centres, P_GAUSS_0, S_GAUSS_0)
    hgl, _, _ = local_rms(centres, P_GAUSS_L, S_GAUSS_L)

    fig, axes = plt.subplots(2, 2, figsize=(10.4, 6.4), constrained_layout=True)
    ax = axes[0, 0]
    ax.plot(low_frequency, np.abs(hs0_low), color=GREY, label="no-delay square")
    ax.plot(low_frequency, np.abs(hsl_low), color=BLUE, linestyle="--", label="delayed square")
    ax.plot(low_frequency, np.abs(hgl_low), color=GREEN, linestyle=":", label="delayed Gaussian")
    ax.set(xlabel="frequency (Hz)", ylabel=r"$|H_{\rm AI}|$", title="a  Resolved low-frequency fringes")
    ax.set_xlim(0.0, 40.0)
    ax.set_ylim(0.0, 4.35)
    ax.grid(alpha=0.22)
    ax.legend(frameon=False)

    ax = axes[0, 1]
    ax.loglog(centres, hs0, color=GREY, label="square, no delay")
    ax.loglog(centres, hsl, color=BLUE, linestyle="--", label="square, $L=150$ m")
    ax.axvline(10.0e3, color=SKY, linewidth=1.0, linestyle="-.")
    ax.set(xlabel="frequency (Hz)", ylabel=r"local RMS of $|H_{\rm AI}|$", title="b  Square finite-pulse envelope")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)

    ax = axes[1, 0]
    ax.loglog(centres, hg0, color=GREY, label="Gaussian, no delay")
    ax.loglog(centres, hgl, color=GREEN, linestyle="--", label="Gaussian, $L=150$ m")
    ax.axvline(10.0e3, color=SKY, linewidth=1.0, linestyle="-.", label="10 kHz reference")
    ax.set(xlabel="frequency (Hz)", ylabel=r"local RMS of $|H_{\rm AI}|$", title="c  Gaussian finite-pulse envelope")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)

    ax = axes[1, 1]
    ax.semilogx(centres, hsl / hs0 - 1.0, color=BLUE, label="square")
    ax.semilogx(centres, hgl / hg0 - 1.0, color=GREEN, linestyle="--", label="Gaussian")
    ax.axhline(0.0, color="black", linewidth=0.7)
    ax.set(xlabel="frequency (Hz)", ylabel="propagation-induced relative change", title="d  Model-A change from no delay")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)
    save_figure(fig, "case_atomic_transfer")


def figure_total_transfer() -> None:
    centres = np.geomspace(0.1, 1.0e5, 620)
    hs_rms, fs, hs_samples = local_rms(centres, P_SQUARE_L, S_SQUARE_L)
    hg_rms, fg, hg_samples = local_rms(centres, P_GAUSS_L, S_GAUSS_L)
    delay_s = delay_phase_transfer(fs, P_SQUARE_L.delay)
    delay_g = delay_phase_transfer(fg, P_GAUSS_L.delay)
    total_s = hs_samples * delay_s
    total_g = hg_samples * delay_g
    total_s_rms = np.sqrt(np.mean(np.abs(total_s) ** 2, axis=1))
    total_g_rms = np.sqrt(np.mean(np.abs(total_g) ** 2, axis=1))
    nu_s = frequency_noise_transfer_function(fs, total_s)
    nu_g = frequency_noise_transfer_function(fg, total_g)
    nu_s_rms = np.sqrt(np.mean(np.abs(nu_s) ** 2, axis=1))
    nu_g_rms = np.sqrt(np.mean(np.abs(nu_g) ** 2, axis=1))
    delay_centre = np.abs(delay_phase_transfer(centres, P_SQUARE_L.delay))

    fig, axes = plt.subplots(1, 3, figsize=(11.1, 3.25), constrained_layout=True)
    ax = axes[0]
    ax.loglog(centres, delay_centre, color=PURPLE)
    ax.loglog(centres, 2.0 * np.pi * centres * P_SQUARE_L.delay, color=GREY, linestyle="--", label=r"$2\pi f\tau_d$")
    ax.set(xlabel="frequency (Hz)", ylabel=r"$|D_d|$", title="a  Propagation phase filter")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)

    ax = axes[1]
    ax.loglog(centres, total_s_rms, color=BLUE, label="square")
    ax.loglog(centres, total_g_rms, color=GREEN, linestyle="--", label="Gaussian")
    ax.set(xlabel="frequency (Hz)", ylabel=r"local RMS of $|H_{\rm src\phi}|$", title="b  Source-phase to atom-phase")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)

    ax = axes[2]
    ax.loglog(centres, nu_s_rms, color=BLUE, label="square")
    ax.loglog(centres, nu_g_rms, color=GREEN, linestyle="--", label="Gaussian")
    ax.axhline(2.0 * np.pi * P_SQUARE_L.delay * np.sqrt(6.0), color=GREY, linestyle=":", linewidth=1.0, label="ideal low-frequency RMS")
    ax.set(xlabel="frequency (Hz)", ylabel=r"local RMS of $|H_\nu|$ (rad/Hz)", title="c  Frequency-noise to atom-phase")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)
    save_figure(fig, "case_total_transfer")


def rms_at(frequency_hz: float, params: PropagationParameters, schedule) -> float:
    offsets = np.linspace(-2.0, 2.0, 401)
    frequencies = np.maximum(frequency_hz + offsets, 1.0e-8)
    response = atom_phase_transfer_function(frequencies, params, schedule)
    return float(np.sqrt(np.mean(np.abs(response) ** 2)))


def write_case_values() -> None:
    delay = P_SQUARE_L.delay
    sq_half, sq_pi = S_SQUARE_L[:2]
    ga_half, ga_pi = S_GAUSS_L[:2]
    lines = [
        f"\\newcommand{{\\CaseDelayUs}}{{{delay * 1e6:.6f}}}",
        f"\\newcommand{{\\CaseSquareHalfOverlapUs}}{{{sq_half.duration * 1e6:.6f}}}",
        f"\\newcommand{{\\CaseSquarePiOverlapUs}}{{{sq_pi.duration * 1e6:.6f}}}",
        f"\\newcommand{{\\CaseSquareHalfScale}}{{{sq_half.area_scale:.6f}}}",
        f"\\newcommand{{\\CaseSquarePiScale}}{{{sq_pi.area_scale:.6f}}}",
        f"\\newcommand{{\\CaseSquareHalfPeak}}{{{sq_half.effective_peak_omega/(2*np.pi*1e3):.4f}}}",
        f"\\newcommand{{\\CaseSquarePiPeak}}{{{sq_pi.effective_peak_omega/(2*np.pi*1e3):.4f}}}",
        f"\\newcommand{{\\CaseGaussHalfSigmaUs}}{{{ga_half.width_parameter * 1e6:.6f}}}",
        f"\\newcommand{{\\CaseGaussPiSigmaUs}}{{{ga_pi.width_parameter * 1e6:.6f}}}",
        f"\\newcommand{{\\CaseGaussHalfSupportUs}}{{{ga_half.duration * 1e6:.6f}}}",
        f"\\newcommand{{\\CaseGaussPiSupportUs}}{{{ga_pi.duration * 1e6:.6f}}}",
        f"\\newcommand{{\\CaseGaussHalfRawPeakRatio}}{{{ga_half.raw_peak_omega/ga_half.input_omega:.6f}}}",
        f"\\newcommand{{\\CaseGaussPiRawPeakRatio}}{{{ga_pi.raw_peak_omega/ga_pi.input_omega:.6f}}}",
        f"\\newcommand{{\\CaseGaussHalfScale}}{{{ga_half.area_scale:.6f}}}",
        f"\\newcommand{{\\CaseGaussPiScale}}{{{ga_pi.area_scale:.6f}}}",
        f"\\newcommand{{\\CaseGaussHalfInputPeak}}{{{ga_half.input_omega/(2*np.pi*1e3):.4f}}}",
        f"\\newcommand{{\\CaseGaussPiInputPeak}}{{{ga_pi.input_omega/(2*np.pi*1e3):.4f}}}",
        f"\\newcommand{{\\CaseGaussHalfEffectivePeak}}{{{ga_half.effective_peak_omega/(2*np.pi*1e3):.4f}}}",
        f"\\newcommand{{\\CaseGaussPiEffectivePeak}}{{{ga_pi.effective_peak_omega/(2*np.pi*1e3):.4f}}}",
        f"\\newcommand{{\\CaseSquareZeroTenK}}{{{rms_at(1e4, P_SQUARE_0, S_SQUARE_0):.6f}}}",
        f"\\newcommand{{\\CaseSquareDelayTenK}}{{{rms_at(1e4, P_SQUARE_L, S_SQUARE_L):.6f}}}",
        f"\\newcommand{{\\CaseGaussZeroTenK}}{{{rms_at(1e4, P_GAUSS_0, S_GAUSS_0):.6f}}}",
        f"\\newcommand{{\\CaseGaussDelayTenK}}{{{rms_at(1e4, P_GAUSS_L, S_GAUSS_L):.6f}}}",
        f"\\newcommand{{\\CaseSquareDelayHundredK}}{{{rms_at(1e5, P_SQUARE_L, S_SQUARE_L):.6e}}}",
        f"\\newcommand{{\\CaseSquareZeroHundredK}}{{{rms_at(1e5, P_SQUARE_0, S_SQUARE_0):.6e}}}",
        f"\\newcommand{{\\CaseGaussDelayHundredK}}{{{rms_at(1e5, P_GAUSS_L, S_GAUSS_L):.6e}}}",
        f"\\newcommand{{\\CaseGaussZeroHundredK}}{{{rms_at(1e5, P_GAUSS_0, S_GAUSS_0):.6e}}}",
        f"\\newcommand{{\\CaseDTenK}}{{{abs(delay_phase_transfer(np.array([1e4]), delay)[0]):.6f}}}",
        f"\\newcommand{{\\CaseDHundredK}}{{{abs(delay_phase_transfer(np.array([1e5]), delay)[0]):.6f}}}",
    ]
    (HERE / "case_values.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    configure_style()
    figure_overlap_and_sensitivity()
    figure_atomic_transfer()
    figure_total_transfer()
    write_case_values()
    print(f"Wrote Model-A square/Gaussian figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
