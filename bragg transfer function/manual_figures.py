"""Generate vector figures for the Bragg transfer-function manual."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from bragg_transfer_function_ui import (
    GAUSSIAN_TRUNCATION_SIGMA,
    InterferometerParameters,
    _gaussian_schedule,
    _gaussian_sigma,
    gaussian_sensitivity_function,
    gaussian_transfer_function,
    sensitivity_function,
    transfer_function,
)


BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
GREY = "#666666"
OUTPUT_DIRECTORY = Path(__file__).resolve().parent / "figures"


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 8,
            "axes.labelsize": 8,
            "axes.titlesize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.linewidth": 0.6,
            "lines.linewidth": 1.3,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.03,
            "pdf.fonttype": 42,
        }
    )


def add_panel_label(axis: plt.Axes, label: str) -> None:
    axis.text(
        -0.13,
        1.04,
        label,
        transform=axis.transAxes,
        fontsize=9,
        fontweight="bold",
        va="top",
    )


def create_pulse_and_sensitivity_figure() -> None:
    tau_half = 25.0e-6
    tau_pi = 50.0e-6
    center_separation = 0.5e-3
    square_free_time = center_separation - 0.5 * (tau_half + tau_pi)
    square_parameters = InterferometerParameters(1, tau_half, tau_pi, square_free_time)
    gaussian_parameters = InterferometerParameters(1, tau_half, tau_pi, center_separation)

    figure = plt.figure(figsize=(7.2, 5.2), constrained_layout=True)
    grid = figure.add_gridspec(2, 2, height_ratios=(0.9, 1.1))
    envelope_axis = figure.add_subplot(grid[0, 0])
    sequence_axis = figure.add_subplot(grid[0, 1])
    sensitivity_axis = figure.add_subplot(grid[1, :])

    normalized_time = np.linspace(-3.0, 3.0, 1600)
    square_envelope = (np.abs(normalized_time) <= 0.5).astype(float)
    sigma_in_fwhm = 1.0 / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    gaussian_envelope = np.exp(-0.5 * (normalized_time / sigma_in_fwhm) ** 2)
    envelope_axis.plot(normalized_time, square_envelope, color=BLUE, label="Square")
    envelope_axis.plot(normalized_time, gaussian_envelope, color=ORANGE, label="Gaussian")
    envelope_axis.annotate(
        "",
        xy=(0.5, 0.5),
        xytext=(-0.5, 0.5),
        arrowprops={"arrowstyle": "<->", "color": "black", "lw": 0.8},
    )
    envelope_axis.text(0.0, 0.56, "FWHM", ha="center", va="bottom")
    envelope_axis.set(xlabel=r"Local time / FWHM", ylabel="Normalized intensity")
    envelope_axis.set_xlim(-2.2, 2.2)
    envelope_axis.set_ylim(-0.04, 1.08)
    envelope_axis.legend(frameon=False, loc="upper right")
    add_panel_label(envelope_axis, "a")

    schematic_centers = np.array([0.0, 1.0, 2.0])
    display_widths = np.array([0.15, 0.30, 0.15])
    for row, shape, color in ((0.66, "Square", BLUE), (0.22, "Gaussian", ORANGE)):
        for index, center in enumerate(schematic_centers):
            width = display_widths[index]
            if shape == "Square":
                x_value = np.array([center - width, center - width, center + width, center + width])
                y_value = np.array([row, row + 0.22, row + 0.22, row])
            else:
                x_value = np.linspace(center - width, center + width, 240)
                local = (x_value - center) / width
                y_value = row + 0.22 * np.exp(
                    -0.5 * (GAUSSIAN_TRUNCATION_SIGMA * local) ** 2
                )
            sequence_axis.plot(x_value, y_value, color=color)
            sequence_axis.fill_between(x_value, row, y_value, color=color, alpha=0.2)
        sequence_axis.text(-0.42, row + 0.1, shape, color=color, ha="right", va="center")
    sequence_axis.annotate(
        r"$T$",
        xy=(1.0, 1.02),
        xytext=(0.0, 1.02),
        ha="center",
        va="bottom",
        arrowprops={"arrowstyle": "<->", "color": GREY, "lw": 0.8},
    )
    sequence_axis.annotate(
        r"$T$",
        xy=(2.0, 1.02),
        xytext=(1.0, 1.02),
        ha="center",
        va="bottom",
        arrowprops={"arrowstyle": "<->", "color": GREY, "lw": 0.8},
    )
    sequence_axis.set_xlim(-0.55, 2.35)
    sequence_axis.set_ylim(0.1, 1.15)
    sequence_axis.set_xticks(schematic_centers, (r"$\pi/2$", r"$\pi$", r"$\pi/2$"))
    sequence_axis.set_yticks([])
    sequence_axis.set_xlabel("Pulse number (free intervals compressed)")
    sequence_axis.spines["left"].set_visible(False)
    add_panel_label(sequence_axis, "b")

    square_time = np.linspace(0.0, square_parameters.total_time, 7000)
    square_center_1 = 0.5 * tau_half
    square_time_relative = square_time - square_center_1
    gaussian_schedule = _gaussian_schedule(gaussian_parameters)
    gaussian_time = np.linspace(gaussian_schedule[0][0], gaussian_schedule[-1][1], 7000)
    gaussian_time_relative = gaussian_time - gaussian_schedule[0][2]
    sensitivity_axis.plot(
        square_time_relative * 1.0e3,
        sensitivity_function(square_time, square_parameters),
        color=BLUE,
        label="Square",
    )
    sensitivity_axis.plot(
        gaussian_time_relative * 1.0e3,
        gaussian_sensitivity_function(gaussian_time, gaussian_parameters),
        color=ORANGE,
        linestyle="--",
        label="Gaussian",
    )
    for center in (0.0, center_separation * 1.0e3, 2.0 * center_separation * 1.0e3):
        sensitivity_axis.axvline(center, color="#BBBBBB", linewidth=0.55, zorder=0)
    sensitivity_axis.axhline(0.0, color="black", linewidth=0.55)
    sensitivity_axis.set(
        xlabel="Time relative to first pulse centre (ms)",
        ylabel=r"Sensitivity $s(t)$",
        ylim=(-1.12, 1.12),
    )
    sensitivity_axis.legend(frameon=False, loc="lower left", ncol=2)
    add_panel_label(sensitivity_axis, "c")

    OUTPUT_DIRECTORY.mkdir(exist_ok=True)
    figure.savefig(OUTPUT_DIRECTORY / "pulse_and_sensitivity.pdf")
    plt.close(figure)


def create_transfer_response_figure() -> None:
    square_parameters = InterferometerParameters(1, 25.0e-6, 50.0e-6, 0.25)
    gaussian_parameters = InterferometerParameters(1, 25.0e-6, 50.0e-6, 0.25)

    figure, axes = plt.subplots(1, 3, figsize=(7.2, 2.5), constrained_layout=True)

    low_frequency = np.linspace(0.0, 40.0, 12001)
    axes[0].plot(
        low_frequency,
        np.abs(transfer_function(low_frequency, square_parameters)),
        color=BLUE,
        label="Square",
    )
    axes[0].plot(
        low_frequency,
        np.abs(gaussian_transfer_function(low_frequency, gaussian_parameters)),
        color=ORANGE,
        linestyle="--",
        label="Gaussian",
    )
    axes[0].set(xlabel="Frequency (Hz)", ylabel=r"$|H_\varphi(f)|$", xlim=(0.0, 40.0))
    axes[0].legend(frameon=False, loc="upper right")
    add_panel_label(axes[0], "a")

    envelope_frequency = np.geomspace(20.0, 100_000.0, 420)
    fringe_offsets = np.linspace(-0.5 / square_parameters.free_time, 0.5 / square_parameters.free_time, 41)
    sampled_frequency = np.maximum(
        envelope_frequency[:, None] + fringe_offsets[None, :], 1.0e-9
    )
    square_samples = transfer_function(sampled_frequency.ravel(), square_parameters).reshape(
        sampled_frequency.shape
    )
    gaussian_samples = gaussian_transfer_function(
        sampled_frequency.ravel(), gaussian_parameters
    ).reshape(sampled_frequency.shape)
    square_rms = np.sqrt(np.mean(np.abs(square_samples) ** 2, axis=1))
    gaussian_rms = np.sqrt(np.mean(np.abs(gaussian_samples) ** 2, axis=1))
    axes[1].loglog(envelope_frequency, square_rms, color=BLUE, label="Square")
    axes[1].loglog(
        envelope_frequency, gaussian_rms, color=ORANGE, linestyle="--", label="Gaussian"
    )
    axes[1].axvline(
        square_parameters.omega_pi_over_2 / (2.0 * np.pi),
        color=GREY,
        linestyle=":",
        linewidth=0.8,
        label=r"$\Omega_{\pi/2}/2\pi$",
    )
    axes[1].set(
        xlabel="Frequency (Hz)",
        ylabel=r"Local RMS of $|H_\varphi|$",
        xlim=(20.0, 100_000.0),
    )
    axes[1].legend(frameon=False, loc="lower left")
    add_panel_label(axes[1], "b")

    local_frequency = np.linspace(9980.0, 10_020.0, 8001)
    square_power = np.abs(transfer_function(local_frequency, square_parameters)) ** 2
    gaussian_power = np.abs(
        gaussian_transfer_function(local_frequency, gaussian_parameters)
    ) ** 2
    axes[2].plot(local_frequency - 10_000.0, square_power, color=BLUE, label="Square")
    axes[2].plot(
        local_frequency - 10_000.0,
        gaussian_power,
        color=ORANGE,
        linestyle="--",
        label="Gaussian",
    )
    axes[2].set(
        xlabel=r"Frequency offset from 10 kHz (Hz)",
        ylabel=r"PSD factor $|H_\varphi(f)|^2$",
        xlim=(-20.0, 20.0),
    )
    axes[2].set_ylim(bottom=0.0)
    axes[2].legend(frameon=False, loc="upper right")
    add_panel_label(axes[2], "c")

    OUTPUT_DIRECTORY.mkdir(exist_ok=True)
    figure.savefig(OUTPUT_DIRECTORY / "transfer_response.pdf")
    plt.close(figure)


def main() -> None:
    configure_style()
    create_pulse_and_sensitivity_figure()
    create_transfer_response_figure()
    print(f"Figures written to {OUTPUT_DIRECTORY}")


if __name__ == "__main__":
    main()
