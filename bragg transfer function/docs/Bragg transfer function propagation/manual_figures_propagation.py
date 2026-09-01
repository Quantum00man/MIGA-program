"""Generate reproducible vector figures for the propagation-aware manual."""

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
    BASE_PHASES,
    C_LIGHT,
    PropagationParameters,
    _local_input_intensity,
    _transition_probability,
    atom_phase_transfer_function,
    build_schedule,
    delay_phase_transfer,
    frequency_noise_transfer_function,
    sensitivity_function,
    source_phase_transfer_function,
)


BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
SKY = "#56B4E9"
PURPLE = "#7B61A8"
GREY = "#606060"


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


def parameters(distance_m: float, model: str) -> PropagationParameters:
    omega = 2.0 * np.pi * 10.0e3
    return PropagationParameters(
        bragg_order=1,
        omega_pi_over_2=omega,
        omega_pi=omega,
        center_separation=0.250,
        distance_to_mirror=distance_m,
        pulse_shape="Square",
        model=model,
    )


P_NO_DELAY = parameters(0.0, "A: area compensated")
P_MODEL_A = parameters(150.0, "A: area compensated")
P_MODEL_B = parameters(150.0, "B: fixed input")
S_NO_DELAY = build_schedule(P_NO_DELAY)
S_MODEL_A = build_schedule(P_MODEL_A)
S_MODEL_B = build_schedule(P_MODEL_B)


def save_figure(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIGURE_DIR / f"{stem}.pdf")
    fig.savefig(FIGURE_DIR / f"{stem}.png", dpi=240, facecolor="white")
    plt.close(fig)


def figure_overlap_and_sensitivity() -> None:
    pulse_a = S_MODEL_A[0]
    pulse_b = S_MODEL_B[0]
    delay = P_MODEL_A.delay
    local_us = np.linspace(-15.0, 40.0, 1600)
    local_s = local_us * 1.0e-6
    forward, reflected = _local_input_intensity(local_s, pulse_a, delay)
    raw_rabi_khz = 10.0 * np.sqrt(forward * reflected)
    corrected_rabi_khz = pulse_a.omega(local_s) / (2.0 * np.pi * 1.0e3)

    fig, axes = plt.subplots(1, 3, figsize=(11.1, 3.25), constrained_layout=True)
    ax = axes[0]
    ax.plot(local_us, forward, color=BLUE, label=r"forward $I(t)$")
    ax.plot(local_us, reflected, color=ORANGE, linestyle="--", label=r"reflected $I(t-\tau_d)$")
    ax.fill_between(
        local_us,
        0.0,
        np.minimum(forward, reflected),
        color=GREEN,
        alpha=0.18,
        label="temporal overlap",
    )
    ax.axvline(0.0, color=BLUE, linewidth=0.8, alpha=0.55)
    ax.axvline(delay * 1.0e6, color=ORANGE, linewidth=0.8, alpha=0.7)
    ax.set(xlabel=r"time relative to command centre ($\mu$s)", ylabel="normalized intensity", title="a  Counter-propagating envelopes")
    ax.set_ylim(-0.04, 1.13)
    ax.grid(alpha=0.22)
    ax.legend(loc="upper right", frameon=False)

    ax = axes[1]
    ax.plot(local_us, raw_rabi_khz, color=ORANGE, linestyle="--", label="model B: raw overlap")
    ax.plot(local_us, corrected_rabi_khz, color=GREEN, label="model A: area compensated")
    ax.axhline(10.0, color=GREY, linestyle=":", linewidth=1.0, label="nominal peak")
    ax.set(
        xlabel=r"time relative to command centre ($\mu$s)",
        ylabel=r"effective $\Omega/2\pi$ (kHz)",
        title=r"b  Effective $\pi/2$ Rabi pulse",
    )
    ax.set_ylim(-0.4, 11.3)
    ax.grid(alpha=0.22)
    ax.legend(loc="lower left", frameon=False)

    ax = axes[2]
    time = np.concatenate(
        [
            np.linspace(S_MODEL_A[0].start, S_MODEL_A[0].end, 280, endpoint=False),
            np.linspace(S_MODEL_A[0].end, S_MODEL_A[1].start, 180, endpoint=False),
            np.linspace(S_MODEL_A[1].start, S_MODEL_A[1].end, 360, endpoint=False),
            np.linspace(S_MODEL_A[1].end, S_MODEL_A[2].start, 180, endpoint=False),
            np.linspace(S_MODEL_A[2].start, S_MODEL_A[2].end, 280),
        ]
    )
    s_a = sensitivity_function(time, P_MODEL_A, S_MODEL_A)
    s_b = sensitivity_function(time, P_MODEL_B, S_MODEL_B)
    ax.plot(time * 1.0e3, s_a, color=GREEN, label="model A")
    ax.plot(time * 1.0e3, s_b, color=ORANGE, linestyle="--", label="model B")
    for pulse in S_MODEL_A:
        ax.axvspan(pulse.start * 1.0e3, pulse.end * 1.0e3, color=SKY, alpha=0.12)
    ax.axhline(0.0, color="black", linewidth=0.7)
    ax.set(xlabel="time (ms)", ylabel=r"$s(t)$", title="c  Sensitivity function")
    ax.set_ylim(-1.13, 1.13)
    ax.grid(alpha=0.22)
    ax.legend(loc="best", frameon=False)
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
            centre_frequencies[:, None] + half_span[:, None] * unit_offsets[None, :]
        )
    else:
        sample_frequency = centre_frequencies[:, None] + offsets[None, :]
    response = atom_phase_transfer_function(sample_frequency.ravel(), params, schedule)
    response = response.reshape(sample_frequency.shape)
    rms = np.sqrt(np.mean(np.abs(response) ** 2, axis=1))
    return rms, sample_frequency, response


def figure_atomic_transfer() -> None:
    low_frequency = np.linspace(0.0, 40.0, 2401)
    h0_low = atom_phase_transfer_function(low_frequency, P_NO_DELAY, S_NO_DELAY)
    ha_low = atom_phase_transfer_function(low_frequency, P_MODEL_A, S_MODEL_A)
    hb_low = atom_phase_transfer_function(low_frequency, P_MODEL_B, S_MODEL_B)

    centres = np.geomspace(20.0, 1.0e5, 520)
    h0_rms, _, _ = local_rms(centres, P_NO_DELAY, S_NO_DELAY)
    ha_rms, _, _ = local_rms(centres, P_MODEL_A, S_MODEL_A)
    hb_rms, _, _ = local_rms(centres, P_MODEL_B, S_MODEL_B)

    fig, axes = plt.subplots(1, 3, figsize=(11.1, 3.25), constrained_layout=True)
    ax = axes[0]
    ax.plot(low_frequency, np.abs(h0_low), color=GREY, label="no delay")
    ax.plot(low_frequency, np.abs(ha_low), color=GREEN, linestyle="--", label="model A")
    ax.plot(low_frequency, np.abs(hb_low), color=ORANGE, linestyle=":", label="model B")
    ax.set(xlabel="frequency (Hz)", ylabel=r"$|H_{\rm AI}|$", title="a  Resolved low-frequency fringes")
    ax.set_xlim(0.0, 40.0)
    ax.set_ylim(0.0, 4.35)
    ax.grid(alpha=0.22)
    ax.legend(frameon=False)

    ax = axes[1]
    ax.loglog(centres, h0_rms, color=GREY, label="no delay")
    ax.loglog(centres, ha_rms, color=GREEN, linestyle="--", label="model A")
    ax.loglog(centres, hb_rms, color=ORANGE, linestyle=":", label="model B")
    ax.axvline(10.0e3, color=SKY, linewidth=1.0, linestyle="-.", label="nominal Rabi rate")
    ax.set(xlabel="frequency (Hz)", ylabel=r"local RMS of $|H_{\rm AI}|$", title="b  Finite-pulse envelope")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)

    ax = axes[2]
    ax.semilogx(centres, ha_rms / h0_rms - 1.0, color=GREEN, label="model A")
    ax.semilogx(centres, hb_rms / h0_rms - 1.0, color=ORANGE, linestyle="--", label="model B")
    ax.axhline(0.0, color="black", linewidth=0.7)
    ax.set(xlabel="frequency (Hz)", ylabel="relative change", title="c  Change relative to no delay")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)
    save_figure(fig, "case_atomic_transfer")


def figure_total_transfer() -> None:
    centres = np.geomspace(0.1, 1.0e5, 620)
    ha_rms, fa, ha_samples = local_rms(centres, P_MODEL_A, S_MODEL_A)
    hb_rms, fb, hb_samples = local_rms(centres, P_MODEL_B, S_MODEL_B)
    delay_a = delay_phase_transfer(fa, P_MODEL_A.delay)
    delay_b = delay_phase_transfer(fb, P_MODEL_B.delay)
    total_a = ha_samples * delay_a
    total_b = hb_samples * delay_b
    total_a_rms = np.sqrt(np.mean(np.abs(total_a) ** 2, axis=1))
    total_b_rms = np.sqrt(np.mean(np.abs(total_b) ** 2, axis=1))
    nu_a = frequency_noise_transfer_function(fa, total_a)
    nu_b = frequency_noise_transfer_function(fb, total_b)
    nu_a_rms = np.sqrt(np.mean(np.abs(nu_a) ** 2, axis=1))
    nu_b_rms = np.sqrt(np.mean(np.abs(nu_b) ** 2, axis=1))
    delay_centre = np.abs(delay_phase_transfer(centres, P_MODEL_A.delay))

    fig, axes = plt.subplots(1, 3, figsize=(11.1, 3.25), constrained_layout=True)
    ax = axes[0]
    ax.loglog(centres, delay_centre, color=PURPLE)
    ax.loglog(centres, 2.0 * np.pi * centres * P_MODEL_A.delay, color=GREY, linestyle="--", label=r"$2\pi f\tau_d$")
    ax.set(xlabel="frequency (Hz)", ylabel=r"$|D_d|$", title="a  Propagation phase filter")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)

    ax = axes[1]
    ax.loglog(centres, total_a_rms, color=GREEN, label="model A")
    ax.loglog(centres, total_b_rms, color=ORANGE, linestyle="--", label="model B")
    ax.set(xlabel="frequency (Hz)", ylabel=r"local RMS of $|H_{\rm src\phi}|$", title="b  Source-phase to atom-phase")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)

    ax = axes[2]
    ax.loglog(centres, nu_a_rms, color=GREEN, label="model A")
    ax.loglog(centres, nu_b_rms, color=ORANGE, linestyle="--", label="model B")
    ax.axhline(
        2.0 * np.pi * P_MODEL_A.delay * np.sqrt(6.0),
        color=GREY,
        linestyle=":",
        linewidth=1.0,
        label="ideal low-frequency RMS",
    )
    ax.set(xlabel="frequency (Hz)", ylabel=r"local RMS of $|H_\nu|$ (rad/Hz)", title="c  Frequency-noise to atom-phase")
    ax.grid(which="both", alpha=0.22)
    ax.legend(frameon=False)
    save_figure(fig, "case_total_transfer")


def rms_at(frequency_hz: float, params: PropagationParameters, schedule) -> float:
    offsets = np.linspace(-2.0, 2.0, 401)
    frequencies = np.maximum(frequency_hz + offsets, 1.0e-8)
    response = atom_phase_transfer_function(frequencies, params, schedule)
    return float(np.sqrt(np.mean(np.abs(response) ** 2)))


def fringe_contrast(schedule) -> float:
    phases = np.linspace(0.0, 2.0 * np.pi, 721)
    probabilities = np.array(
        [
            _transition_probability(
                schedule, (BASE_PHASES[0], BASE_PHASES[1], float(phase))
            )
            for phase in phases
        ]
    )
    return float(np.max(probabilities) - np.min(probabilities))


def write_case_values() -> None:
    delay = P_MODEL_A.delay
    pulse_a_half, pulse_a_pi = S_MODEL_A[:2]
    pulse_b_half, pulse_b_pi = S_MODEL_B[:2]
    h0_10k = rms_at(10.0e3, P_NO_DELAY, S_NO_DELAY)
    ha_10k = rms_at(10.0e3, P_MODEL_A, S_MODEL_A)
    hb_10k = rms_at(10.0e3, P_MODEL_B, S_MODEL_B)
    ha_100k = rms_at(100.0e3, P_MODEL_A, S_MODEL_A)
    hb_100k = rms_at(100.0e3, P_MODEL_B, S_MODEL_B)
    d10 = abs(delay_phase_transfer(np.array([10.0e3]), delay)[0])
    d100 = abs(delay_phase_transfer(np.array([100.0e3]), delay)[0])
    lines = [
        f"\\newcommand{{\\CaseDelayUs}}{{{delay * 1e6:.6f}}}",
        f"\\newcommand{{\\CaseHalfOverlapUs}}{{{pulse_b_half.duration * 1e6:.6f}}}",
        f"\\newcommand{{\\CasePiOverlapUs}}{{{pulse_b_pi.duration * 1e6:.6f}}}",
        f"\\newcommand{{\\CaseHalfAreaRatio}}{{{pulse_b_half.raw_area / pulse_b_half.target_area:.6f}}}",
        f"\\newcommand{{\\CasePiAreaRatio}}{{{pulse_b_pi.raw_area / pulse_b_pi.target_area:.6f}}}",
        f"\\newcommand{{\\CaseHalfScale}}{{{pulse_a_half.area_scale:.6f}}}",
        f"\\newcommand{{\\CasePiScale}}{{{pulse_a_pi.area_scale:.6f}}}",
        f"\\newcommand{{\\CaseHalfPeakA}}{{{pulse_a_half.effective_peak_omega/(2*np.pi*1e3):.4f}}}",
        f"\\newcommand{{\\CasePiPeakA}}{{{pulse_a_pi.effective_peak_omega/(2*np.pi*1e3):.4f}}}",
        f"\\newcommand{{\\CaseContrastB}}{{{fringe_contrast(S_MODEL_B):.6f}}}",
        f"\\newcommand{{\\CaseHZeroTenK}}{{{h0_10k:.6f}}}",
        f"\\newcommand{{\\CaseHATenK}}{{{ha_10k:.6f}}}",
        f"\\newcommand{{\\CaseHBTenK}}{{{hb_10k:.6f}}}",
        f"\\newcommand{{\\CaseHAHundredK}}{{{ha_100k:.6e}}}",
        f"\\newcommand{{\\CaseHBHundredK}}{{{hb_100k:.6e}}}",
        f"\\newcommand{{\\CaseDTenK}}{{{d10:.6f}}}",
        f"\\newcommand{{\\CaseDHundredK}}{{{d100:.6f}}}",
    ]
    (HERE / "case_values.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    configure_style()
    figure_overlap_and_sensitivity()
    figure_atomic_transfer()
    figure_total_transfer()
    write_case_values()
    print(f"Wrote propagation-manual figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
