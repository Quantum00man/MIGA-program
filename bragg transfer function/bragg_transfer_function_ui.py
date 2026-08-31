"""Finite-pulse Bragg atom-interferometer transfer-function calculator.

Model assumptions
-----------------
* Resonant square or Gaussian pulses in an effective two-level approximation.
* A pi/2 - pi - pi/2 Mach-Zehnder sequence.
* The first and third pi/2 pulses have the same duration.
* For square pulses, T is the free-evolution time between pulse edges.
* For Gaussian pulses, the entered widths are optical-intensity FWHM values and
  T is the pulse-center separation.  The effective Bragg Rabi envelope is
  assumed to be proportional to the optical-intensity envelope.
* Bragg order n multiplies the phase response, as in the MIGA convention:
      Delta phi_AT = n * Delta varphi * ds/dt

The square-pulse transfer function is evaluated analytically with a stable
sinc-based formulation.  The Gaussian transfer function is evaluated with
Gauss-Legendre quadrature over +/-6 standard deviations per pulse.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


@dataclass(frozen=True)
class InterferometerParameters:
    """Physical parameters in SI units."""

    bragg_order: int
    tau_pi_over_2: float
    tau_pi: float
    free_time: float

    def validate(self) -> None:
        if self.bragg_order < 1:
            raise ValueError("Bragg order must be a positive integer.")
        if not np.all(
            np.isfinite([self.tau_pi_over_2, self.tau_pi, self.free_time])
        ):
            raise ValueError("Pulse durations and free-evolution time must be finite.")
        if self.tau_pi_over_2 <= 0.0:
            raise ValueError("The pi/2 pulse duration must be positive.")
        if self.tau_pi <= 0.0:
            raise ValueError("The pi pulse duration must be positive.")
        if self.free_time < 0.0:
            raise ValueError("Free-evolution time T cannot be negative.")

    @property
    def omega_pi_over_2(self) -> float:
        return np.pi / (2.0 * self.tau_pi_over_2)

    @property
    def omega_pi(self) -> float:
        return np.pi / self.tau_pi

    @property
    def pulse_2_start(self) -> float:
        return self.tau_pi_over_2 + self.free_time

    @property
    def pulse_2_end(self) -> float:
        return self.pulse_2_start + self.tau_pi

    @property
    def pulse_3_start(self) -> float:
        return self.pulse_2_end + self.free_time

    @property
    def total_time(self) -> float:
        return self.pulse_3_start + self.tau_pi_over_2


def sensitivity_function(
    time_s: np.ndarray | float, parameters: InterferometerParameters
) -> np.ndarray:
    """Return the finite-pulse sensitivity function s(t)."""

    parameters.validate()
    t = np.asarray(time_s, dtype=float)
    s = np.zeros_like(t)

    tau_half = parameters.tau_pi_over_2
    omega_half = parameters.omega_pi_over_2
    omega_pi = parameters.omega_pi
    pulse_2_start = parameters.pulse_2_start
    pulse_2_end = parameters.pulse_2_end
    pulse_3_start = parameters.pulse_3_start
    total_time = parameters.total_time

    mask = (t >= 0.0) & (t < tau_half)
    s[mask] = np.sin(omega_half * t[mask])

    mask = (t >= tau_half) & (t < pulse_2_start)
    s[mask] = 1.0

    mask = (t >= pulse_2_start) & (t < pulse_2_end)
    s[mask] = np.cos(omega_pi * (t[mask] - pulse_2_start))

    mask = (t >= pulse_2_end) & (t < pulse_3_start)
    s[mask] = -1.0

    mask = (t >= pulse_3_start) & (t < total_time)
    s[mask] = -np.cos(omega_half * (t[mask] - pulse_3_start))

    return s


def _complex_exponential_integral(q: np.ndarray, duration: float) -> np.ndarray:
    """Compute integral_0^duration exp(i*q*t) dt without removable singularities."""

    return (
        duration
        * np.exp(0.5j * q * duration)
        * np.sinc(q * duration / (2.0 * np.pi))
    )


def _cosine_fourier_integral(
    omega: np.ndarray, rabi_omega: float, duration: float
) -> np.ndarray:
    """Compute integral cos(Omega*t) exp(-i*omega*t) dt on [0, duration]."""

    positive = _complex_exponential_integral(rabi_omega - omega, duration)
    negative = _complex_exponential_integral(-rabi_omega - omega, duration)
    return 0.5 * (positive + negative)


def _sine_fourier_integral(
    omega: np.ndarray, rabi_omega: float, duration: float
) -> np.ndarray:
    """Compute integral sin(Omega*t) exp(-i*omega*t) dt on [0, duration]."""

    positive = _complex_exponential_integral(rabi_omega - omega, duration)
    negative = _complex_exponential_integral(-rabi_omega - omega, duration)
    return (positive - negative) / (2.0j)


def transfer_function(
    frequency_hz: np.ndarray | float, parameters: InterferometerParameters
) -> np.ndarray:
    """Return the complex laser-phase transfer function H_phi(f)."""

    parameters.validate()
    frequency = np.asarray(frequency_hz, dtype=float)
    omega = 2.0 * np.pi * frequency

    tau_half = parameters.tau_pi_over_2
    tau_pi = parameters.tau_pi
    omega_half = parameters.omega_pi_over_2
    omega_pi = parameters.omega_pi

    first_pulse = omega_half * _cosine_fourier_integral(
        omega, omega_half, tau_half
    )
    middle_pulse = (
        -omega_pi
        * np.exp(-1.0j * omega * parameters.pulse_2_start)
        * _sine_fourier_integral(omega, omega_pi, tau_pi)
    )
    final_pulse = (
        omega_half
        * np.exp(-1.0j * omega * parameters.pulse_3_start)
        * _sine_fourier_integral(omega, omega_half, tau_half)
    )

    result = parameters.bragg_order * (first_pulse + middle_pulse + final_pulse)
    # Enforce the exact DC identity H(0) = integral(ds/dt) dt = 0.
    return np.where(omega == 0.0, 0.0 + 0.0j, result)


def instantaneous_pulse_magnitude(
    frequency_hz: np.ndarray | float, bragg_order: int, free_time: float
) -> np.ndarray:
    """Return n*4*sin^2(omega*T/2), the zero-duration pulse limit."""

    omega = 2.0 * np.pi * np.asarray(frequency_hz, dtype=float)
    return bragg_order * 4.0 * np.sin(0.5 * omega * free_time) ** 2


GAUSSIAN_TRUNCATION_SIGMA = 6.0


def _gaussian_sigma(fwhm: float) -> float:
    """Convert intensity FWHM to the standard deviation of the Gaussian envelope."""

    return fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))


def _gaussian_schedule(
    parameters: InterferometerParameters,
) -> list[tuple[float, float, float, float, float]]:
    """Return (start, end, center, sigma, pulse area) for three Gaussian pulses.

    Gaussian T is the center-to-center separation.  The numerical representation
    is truncated at +/- GAUSSIAN_TRUNCATION_SIGMA standard deviations.
    """

    sigma_half = _gaussian_sigma(parameters.tau_pi_over_2)
    sigma_pi = _gaussian_sigma(parameters.tau_pi)
    half_window_half = GAUSSIAN_TRUNCATION_SIGMA * sigma_half
    half_window_pi = GAUSSIAN_TRUNCATION_SIGMA * sigma_pi

    center_1 = half_window_half
    center_2 = center_1 + parameters.free_time
    center_3 = center_2 + parameters.free_time
    schedule = [
        (
            center_1 - half_window_half,
            center_1 + half_window_half,
            center_1,
            sigma_half,
            np.pi / 2.0,
        ),
        (
            center_2 - half_window_pi,
            center_2 + half_window_pi,
            center_2,
            sigma_pi,
            np.pi,
        ),
        (
            center_3 - half_window_half,
            center_3 + half_window_half,
            center_3,
            sigma_half,
            np.pi / 2.0,
        ),
    ]
    if schedule[0][1] > schedule[1][0] or schedule[1][1] > schedule[2][0]:
        minimum_separation = half_window_half + half_window_pi
        raise ValueError(
            "Gaussian pulses overlap within the +/-6 sigma numerical windows. "
            f"Use T >= {minimum_separation * 1.0e3:.6g} ms, or use a full "
            "overlapping-pulse dynamical model."
        )
    return schedule


def _erf_array(values: np.ndarray) -> np.ndarray:
    """Vectorized error function without adding a SciPy dependency."""

    flat = np.asarray(values, dtype=float).ravel()
    result = np.fromiter((math.erf(value) for value in flat), dtype=float)
    return result.reshape(np.shape(values))


def _gaussian_rabi_and_area(
    local_time: np.ndarray, sigma: float, total_area: float
) -> tuple[np.ndarray, np.ndarray]:
    """Return Omega(t) and accumulated area for a truncated Gaussian pulse."""

    edge_erf = math.erf(GAUSSIAN_TRUNCATION_SIGMA / np.sqrt(2.0))
    normalization = sigma * np.sqrt(2.0 * np.pi) * edge_erf
    rabi = total_area / normalization * np.exp(-0.5 * (local_time / sigma) ** 2)
    accumulated_area = total_area * (
        _erf_array(local_time / (np.sqrt(2.0) * sigma)) + edge_erf
    ) / (2.0 * edge_erf)
    return rabi, accumulated_area


def gaussian_sensitivity_function(
    time_s: np.ndarray | float, parameters: InterferometerParameters
) -> np.ndarray:
    """Return s(t) for three separated Gaussian intensity pulses."""

    parameters.validate()
    schedule = _gaussian_schedule(parameters)
    t = np.asarray(time_s, dtype=float)
    s = np.zeros_like(t)

    first_start, first_end, first_center, first_sigma, first_area = schedule[0]
    middle_start, middle_end, middle_center, middle_sigma, middle_area = schedule[1]
    final_start, final_end, final_center, final_sigma, final_area = schedule[2]

    mask = (t >= first_start) & (t < first_end)
    _, area = _gaussian_rabi_and_area(
        t[mask] - first_center, first_sigma, first_area
    )
    s[mask] = np.sin(area)

    mask = (t >= first_end) & (t < middle_start)
    s[mask] = 1.0

    mask = (t >= middle_start) & (t < middle_end)
    _, area = _gaussian_rabi_and_area(
        t[mask] - middle_center, middle_sigma, middle_area
    )
    s[mask] = np.cos(area)

    mask = (t >= middle_end) & (t < final_start)
    s[mask] = -1.0

    mask = (t >= final_start) & (t < final_end)
    _, area = _gaussian_rabi_and_area(
        t[mask] - final_center, final_sigma, final_area
    )
    s[mask] = -np.cos(area)
    return s


def _weighted_fourier_integral(
    omega: np.ndarray,
    absolute_time: np.ndarray,
    weighted_derivative: np.ndarray,
) -> np.ndarray:
    """Evaluate a quadrature Fourier integral in bounded-memory chunks."""

    result = np.empty(omega.size, dtype=complex)
    chunk_size = 2048
    for start in range(0, omega.size, chunk_size):
        stop = min(start + chunk_size, omega.size)
        phase = np.exp(-1.0j * omega[start:stop, None] * absolute_time[None, :])
        result[start:stop] = phase @ weighted_derivative
    return result


def gaussian_transfer_function(
    frequency_hz: np.ndarray | float, parameters: InterferometerParameters
) -> np.ndarray:
    """Numerically evaluate H_phi for separated Gaussian intensity pulses."""

    parameters.validate()
    schedule = _gaussian_schedule(parameters)
    frequency = np.asarray(frequency_hz, dtype=float)
    original_shape = frequency.shape
    flat_frequency = frequency.ravel()
    omega = 2.0 * np.pi * flat_frequency
    maximum_frequency = float(np.max(np.abs(flat_frequency))) if flat_frequency.size else 0.0
    result = np.zeros(flat_frequency.size, dtype=complex)
    quadrature_cache: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    for pulse_index, (start, end, center, sigma, total_area) in enumerate(schedule):
        duration = end - start
        quadrature_order = max(256, int(np.ceil(20.0 * maximum_frequency * duration)) + 64)
        if quadrature_order > 4096:
            raise ValueError(
                "The selected maximum frequency and Gaussian pulse width require "
                "more than 4096 quadrature nodes. Reduce the maximum frequency "
                "or use a narrower pulse."
            )
        if quadrature_order not in quadrature_cache:
            nodes, weights = np.polynomial.legendre.leggauss(quadrature_order)
            quadrature_cache[quadrature_order] = (nodes, weights)
        else:
            nodes, weights = quadrature_cache[quadrature_order]

        half_window = 0.5 * duration
        local_time = half_window * nodes
        quadrature_weights = half_window * weights
        rabi, accumulated_area = _gaussian_rabi_and_area(
            local_time, sigma, total_area
        )
        if pulse_index == 0:
            derivative = rabi * np.cos(accumulated_area)
        elif pulse_index == 1:
            derivative = -rabi * np.sin(accumulated_area)
        else:
            derivative = rabi * np.sin(accumulated_area)
        result += _weighted_fourier_integral(
            omega,
            center + local_time,
            quadrature_weights * derivative,
        )

    result *= parameters.bragg_order
    result = np.where(omega == 0.0, 0.0 + 0.0j, result)
    return result.reshape(original_shape)


def pulse_envelope(
    time_s: np.ndarray, parameters: InterferometerParameters, pulse_shape: str
) -> np.ndarray:
    """Return the effective Rabi envelope, proportional to Bragg pulse intensity."""

    t = np.asarray(time_s, dtype=float)
    envelope = np.zeros_like(t)
    if pulse_shape == "Square":
        mask = (t >= 0.0) & (t < parameters.tau_pi_over_2)
        envelope[mask] = parameters.omega_pi_over_2
        mask = (t >= parameters.pulse_2_start) & (t < parameters.pulse_2_end)
        envelope[mask] = parameters.omega_pi
        mask = (t >= parameters.pulse_3_start) & (t < parameters.total_time)
        envelope[mask] = parameters.omega_pi_over_2
        return envelope

    for start, end, center, sigma, total_area in _gaussian_schedule(parameters):
        mask = (t >= start) & (t <= end)
        rabi, _ = _gaussian_rabi_and_area(t[mask] - center, sigma, total_area)
        envelope[mask] += rabi
    return envelope


def gaussian_plot_grid(parameters: InterferometerParameters) -> np.ndarray:
    """Return a plot grid resolving all Gaussian pulses and free intervals."""

    schedule = _gaussian_schedule(parameters)
    segments: list[np.ndarray] = []
    for index, (start, end, _center, _sigma, _area) in enumerate(schedule):
        segments.append(np.linspace(start, end, 350, endpoint=False))
        if index < len(schedule) - 1:
            next_start = schedule[index + 1][0]
            segments.append(np.linspace(end, next_start, 100, endpoint=False))
    segments.append(np.array([schedule[-1][1]]))
    return np.unique(np.concatenate(segments))


def _sensitivity_plot_grid(parameters: InterferometerParameters) -> np.ndarray:
    """Create a grid that resolves all pulses even when T is much longer."""

    padding = max(0.025 * parameters.total_time, 0.25 * parameters.tau_pi_over_2)
    segments = [
        np.linspace(-padding, 0.0, 30, endpoint=False),
        np.linspace(0.0, parameters.tau_pi_over_2, 250, endpoint=False),
        np.linspace(
            parameters.tau_pi_over_2,
            parameters.pulse_2_start,
            100,
            endpoint=False,
        ),
        np.linspace(
            parameters.pulse_2_start,
            parameters.pulse_2_end,
            350,
            endpoint=False,
        ),
        np.linspace(
            parameters.pulse_2_end,
            parameters.pulse_3_start,
            100,
            endpoint=False,
        ),
        np.linspace(
            parameters.pulse_3_start,
            parameters.total_time,
            250,
            endpoint=False,
        ),
        np.linspace(parameters.total_time, parameters.total_time + padding, 30),
    ]
    return np.unique(np.concatenate(segments))


def _time_axis_scale(total_time: float) -> tuple[float, str]:
    if total_time < 1.0e-3:
        return 1.0e6, "us"
    if total_time < 1.0:
        return 1.0e3, "ms"
    return 1.0, "s"


class BraggTransferFunctionApp:
    """Tkinter user interface for the calculator."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Finite-Pulse Bragg Transfer Function")
        self.root.geometry("1240x900")
        self.root.minsize(1000, 760)

        self.pulse_shape = tk.StringVar(value="Square")
        self.bragg_order = tk.StringVar(value="1")
        self.tau_half_us = tk.StringVar(value="25")
        self.tau_pi_us = tk.StringVar(value="50")
        self.free_time_ms = tk.StringVar(value="250")
        self.frequency_min_hz = tk.StringVar(value="0.1")
        self.frequency_max_hz = tk.StringVar(value="100000")
        self.frequency_points = tk.StringVar(value="3000")
        self.show_instantaneous = tk.BooleanVar(value=True)
        self.status_text = tk.StringVar(value="Ready")
        self.model_note = tk.StringVar(
            value="Square mode: T is the free time between pulse edges."
        )

        self._configure_style()
        self._build_layout()
        self.calculate()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Status.TLabel", foreground="#304860")

    def _build_layout(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        controls = ttk.Frame(self.root, padding=(14, 14, 10, 14))
        controls.grid(row=0, column=0, sticky="ns")
        controls.columnconfigure(0, weight=1)

        ttk.Label(
            controls,
            text="Bragg Transfer Function",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Label(
            controls,
            text="Finite resonant pulses\nEffective two-level model",
            foreground="#536878",
        ).grid(row=1, column=0, sticky="w", pady=(0, 14))

        sequence_box = ttk.LabelFrame(
            controls, text="Pulse sequence", style="Section.TLabelframe", padding=10
        )
        sequence_box.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        sequence_box.columnconfigure(1, weight=1)
        ttk.Label(sequence_box, text="Pulse shape").grid(
            row=0, column=0, sticky="w", pady=4
        )
        shape_selector = ttk.Combobox(
            sequence_box,
            textvariable=self.pulse_shape,
            values=("Square", "Gaussian"),
            state="readonly",
            width=13,
        )
        shape_selector.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=4)
        shape_selector.bind("<<ComboboxSelected>>", lambda _event: self.calculate())
        self._add_entry(sequence_box, 1, "Bragg order n", self.bragg_order, "integer")
        self._add_entry(
            sequence_box, 2, "pi/2 duration / FWHM", self.tau_half_us, "us"
        )
        self._add_entry(sequence_box, 3, "pi duration / FWHM", self.tau_pi_us, "us")
        self._add_entry(
            sequence_box, 4, "Interrogation time T", self.free_time_ms, "ms"
        )

        frequency_box = ttk.LabelFrame(
            controls, text="Frequency grid", style="Section.TLabelframe", padding=10
        )
        frequency_box.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self._add_entry(
            frequency_box, 0, "Minimum frequency", self.frequency_min_hz, "Hz"
        )
        self._add_entry(
            frequency_box, 1, "Maximum frequency", self.frequency_max_hz, "Hz"
        )
        self._add_entry(
            frequency_box, 2, "Frequency points", self.frequency_points, "integer"
        )

        ttk.Checkbutton(
            controls,
            text="Show instantaneous-pulse limit",
            variable=self.show_instantaneous,
            command=self.calculate,
        ).grid(row=4, column=0, sticky="w", pady=(2, 10))

        button_row = ttk.Frame(controls)
        button_row.grid(row=5, column=0, sticky="ew")
        button_row.columnconfigure((0, 1), weight=1)
        ttk.Button(button_row, text="Calculate", command=self.calculate).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(button_row, text="Save figure...", command=self.save_figure).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        ttk.Separator(controls).grid(row=6, column=0, sticky="ew", pady=14)
        ttk.Label(
            controls,
            textvariable=self.status_text,
            style="Status.TLabel",
            justify="left",
            wraplength=270,
        ).grid(row=7, column=0, sticky="nw")

        ttk.Label(
            controls,
            textvariable=self.model_note,
            foreground="#6a6a6a",
            justify="left",
            wraplength=270,
        ).grid(row=8, column=0, sticky="sw", pady=(18, 0))
        controls.rowconfigure(8, weight=1)

        plot_frame = ttk.Frame(self.root, padding=(0, 10, 12, 10))
        plot_frame.grid(row=0, column=1, sticky="nsew")
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)

        self.figure = Figure(figsize=(9.0, 8.3), dpi=100, constrained_layout=True)
        self.pulse_axes = self.figure.add_subplot(311)
        self.sensitivity_axes = self.figure.add_subplot(312)
        self.transfer_axes = self.figure.add_subplot(313)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame, pack_toolbar=False)
        toolbar.update()
        toolbar.grid(row=1, column=0, sticky="ew")

        self.root.bind("<Return>", lambda _event: self.calculate())

    @staticmethod
    def _add_entry(
        parent: ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.StringVar,
        unit: str,
    ) -> None:
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable, width=13).grid(
            row=row, column=1, sticky="ew", padx=(10, 6), pady=4
        )
        ttk.Label(parent, text=unit, foreground="#606060").grid(
            row=row, column=2, sticky="w", pady=4
        )

    def _read_inputs(
        self,
    ) -> tuple[InterferometerParameters, float, float, int]:
        try:
            order_float = float(self.bragg_order.get())
            tau_half = float(self.tau_half_us.get()) * 1.0e-6
            tau_pi = float(self.tau_pi_us.get()) * 1.0e-6
            free_time = float(self.free_time_ms.get()) * 1.0e-3
            frequency_min = float(self.frequency_min_hz.get())
            frequency_max = float(self.frequency_max_hz.get())
            points_float = float(self.frequency_points.get())
        except ValueError as exc:
            raise ValueError("All fields must contain valid numbers.") from exc

        if not np.isfinite(order_float) or not order_float.is_integer():
            raise ValueError("Bragg order must be an integer.")
        order = int(order_float)
        parameters = InterferometerParameters(
            bragg_order=order,
            tau_pi_over_2=tau_half,
            tau_pi=tau_pi,
            free_time=free_time,
        )
        parameters.validate()
        if not np.isfinite(points_float) or not points_float.is_integer():
            raise ValueError("Frequency points must be an integer.")
        points = int(points_float)

        if frequency_min <= 0.0:
            raise ValueError("Minimum frequency must be greater than zero for a log axis.")
        if not np.all(np.isfinite([frequency_min, frequency_max])):
            raise ValueError("Frequency limits must be finite.")
        if frequency_max <= frequency_min:
            raise ValueError("Maximum frequency must exceed minimum frequency.")
        if not 100 <= points <= 100_000:
            raise ValueError("Frequency points must be between 100 and 100000.")
        return parameters, frequency_min, frequency_max, points

    def _draw_pulse_schematic(
        self, parameters: InterferometerParameters, pulse_shape: str
    ) -> None:
        """Draw pulse shapes with compressed gaps and physical-time readout."""

        self.pulse_axes.clear()
        durations = np.array(
            [
                parameters.tau_pi_over_2,
                parameters.tau_pi,
                parameters.tau_pi_over_2,
            ]
        )
        areas = np.array([np.pi / 2.0, np.pi, np.pi / 2.0])
        centers = np.array([0.0, 1.0, 2.0])
        colors = ("#6a5acd", "#d17b0f", "#6a5acd")
        display_half_widths = 0.18 * durations / np.max(durations)

        if pulse_shape == "Square":
            peak_rates = np.array(
                [
                    parameters.omega_pi_over_2,
                    parameters.omega_pi,
                    parameters.omega_pi_over_2,
                ]
            )
            physical_intervals = np.array(
                [
                    [0.0, parameters.tau_pi_over_2],
                    [parameters.pulse_2_start, parameters.pulse_2_end],
                    [parameters.pulse_3_start, parameters.total_time],
                ]
            )
            physical_centers = np.mean(physical_intervals, axis=1)
            t_arrow_edges = [
                (centers[0] + display_half_widths[0], centers[1] - display_half_widths[1]),
                (centers[1] + display_half_widths[1], centers[2] - display_half_widths[2]),
            ]
            t_definition = "edge gap"
        else:
            peak_rates = []
            for duration, area in zip(durations, areas):
                sigma = _gaussian_sigma(float(duration))
                rabi, _ = _gaussian_rabi_and_area(np.array([0.0]), sigma, float(area))
                peak_rates.append(rabi[0])
            peak_rates = np.asarray(peak_rates)
            gaussian_schedule = _gaussian_schedule(parameters)
            physical_intervals = np.array(
                [[item[0], item[1]] for item in gaussian_schedule]
            )
            physical_centers = np.array([item[2] for item in gaussian_schedule])
            t_arrow_edges = [(centers[0], centers[1]), (centers[1], centers[2])]
            t_definition = "center spacing"
        normalized_peaks = peak_rates / np.max(peak_rates)
        physical_reference = physical_centers[0]
        relative_physical_intervals = physical_intervals - physical_reference
        relative_physical_centers = physical_centers - physical_reference

        for index, (center, duration, peak, color) in enumerate(
            zip(centers, durations, normalized_peaks, colors)
        ):
            display_half_width = display_half_widths[index]
            if pulse_shape == "Square":
                x = np.array(
                    [
                        center - display_half_width,
                        center - display_half_width,
                        center + display_half_width,
                        center + display_half_width,
                    ]
                )
                y = np.array([0.0, peak, peak, 0.0])
            else:
                x = np.linspace(
                    center - display_half_width, center + display_half_width, 300
                )
                sigma_coordinate = (x - center) / display_half_width
                y = peak * np.exp(
                    -0.5 * (GAUSSIAN_TRUNCATION_SIGMA * sigma_coordinate) ** 2
                )
            self.pulse_axes.plot(x, y, color=color, linewidth=2.0)
            self.pulse_axes.fill_between(x, 0.0, y, color=color, alpha=0.22)

            if pulse_shape == "Square":
                fwhm_half_width = display_half_width
            else:
                sigma = _gaussian_sigma(float(duration))
                fwhm_half_width = display_half_width * (
                    0.5 * duration
                ) / (GAUSSIAN_TRUNCATION_SIGMA * sigma)
            arrow_height = 0.5 * peak
            self.pulse_axes.annotate(
                "",
                xy=(center + fwhm_half_width, arrow_height),
                xytext=(center - fwhm_half_width, arrow_height),
                arrowprops={"arrowstyle": "<->", "color": "#202020", "lw": 1.15},
            )
            pulse_name = "pi" if index == 1 else "pi/2"
            self.pulse_axes.text(
                center,
                arrow_height + 0.09,
                f"{pulse_name} FWHM = {duration * 1.0e6:.6g} us",
                ha="center",
                va="bottom",
                fontsize=8.5,
                color="#202020",
            )

        for left, right in t_arrow_edges:
            self.pulse_axes.annotate(
                "",
                xy=(right, 1.18),
                xytext=(left, 1.18),
                arrowprops={"arrowstyle": "<->", "color": "#1769aa", "lw": 1.25},
            )
            self.pulse_axes.text(
                0.5 * (left + right),
                1.22,
                f"T = {parameters.free_time * 1.0e3:.6g} ms",
                ha="center",
                va="bottom",
                fontsize=9,
                color="#1769aa",
            )

        self.pulse_axes.axhline(0.0, color="#333333", linewidth=0.8)
        self.pulse_axes.set_xlim(-0.45, 2.45)
        self.pulse_axes.set_ylim(-0.08, 1.42)
        center_tick_labels = [
            f"Pulse {index + 1}\n{center_time * 1.0e3:.6g} ms"
            for index, center_time in enumerate(relative_physical_centers)
        ]
        self.pulse_axes.set_xticks(centers, center_tick_labels)
        self.pulse_axes.set_xlabel(
            "Relative time (ms; first pulse centered at 0, free gaps compressed)"
        )
        self.pulse_axes.set_ylabel("Normalized intensity")
        self.pulse_axes.set_title(
            f"3-Pulse {pulse_shape} Sequence: FWHM and T ({t_definition})"
        )
        self.pulse_axes.grid(True, axis="y", alpha=0.22)

        visual_anchors = np.ravel(
            np.column_stack(
                (
                    centers - display_half_widths,
                    centers + display_half_widths,
                )
            )
        )
        physical_anchors = np.ravel(relative_physical_intervals)

        def format_pulse_coordinates(x_value: float, y_value: float) -> str:
            physical_time = np.interp(x_value, visual_anchors, physical_anchors)
            return (
                f"time={physical_time * 1.0e3:.9g} ms, "
                f"normalized intensity={y_value:.6g}"
            )

        self.pulse_axes.format_coord = format_pulse_coordinates

    def calculate(self) -> None:
        try:
            parameters, frequency_min, frequency_max, points = self._read_inputs()
            pulse_shape = self.pulse_shape.get()
            frequencies = np.geomspace(frequency_min, frequency_max, points)
            if pulse_shape == "Square":
                response = transfer_function(frequencies, parameters)
                time = _sensitivity_plot_grid(parameters)
                sensitivity = sensitivity_function(time, parameters)
                total_time = parameters.total_time
                pulse_intervals = [
                    (0.0, parameters.tau_pi_over_2),
                    (parameters.pulse_2_start, parameters.pulse_2_end),
                    (parameters.pulse_3_start, parameters.total_time),
                ]
                rate_half = parameters.omega_pi_over_2
                rate_pi = parameters.omega_pi
                timing_description = "T: free time between pulse edges"
                integration_description = "Transfer integral: analytic"
                self.model_note.set(
                    "Square mode: T is the free time between pulse edges. "
                    "Bragg order n scales the phase response."
                )
            elif pulse_shape == "Gaussian":
                schedule = _gaussian_schedule(parameters)
                response = gaussian_transfer_function(frequencies, parameters)
                time = gaussian_plot_grid(parameters)
                sensitivity = gaussian_sensitivity_function(time, parameters)
                total_time = schedule[-1][1]
                pulse_intervals = [(item[0], item[1]) for item in schedule]
                rate_half = _gaussian_rabi_and_area(
                    np.array([0.0]), schedule[0][3], schedule[0][4]
                )[0][0]
                rate_pi = _gaussian_rabi_and_area(
                    np.array([0.0]), schedule[1][3], schedule[1][4]
                )[0][0]
                timing_description = "T: pulse-center separation"
                integration_description = "Transfer integral: numerical"
                self.model_note.set(
                    "Gaussian mode: FWHM refers to optical intensity and T is "
                    "the pulse-center separation. Effective Bragg Rabi frequency "
                    "is assumed proportional to intensity."
                )
            else:
                raise ValueError("Unsupported pulse shape.")
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc), parent=self.root)
            return

        magnitude = np.abs(response)
        time_scale, time_unit = _time_axis_scale(total_time)
        self._draw_pulse_schematic(parameters, pulse_shape)

        self.sensitivity_axes.clear()
        self.sensitivity_axes.plot(
            time * time_scale,
            sensitivity,
            color="#1769aa",
            linewidth=2.0,
            label="Finite-pulse s(t)",
        )
        for start, end in pulse_intervals:
            self.sensitivity_axes.axvspan(
                start * time_scale,
                end * time_scale,
                color="#ffb74d",
                alpha=0.22,
                linewidth=0,
            )
        self.sensitivity_axes.axhline(0.0, color="#333333", linewidth=0.8)
        self.sensitivity_axes.set_title("Sensitivity Function")
        self.sensitivity_axes.set_xlabel(f"Time ({time_unit})")
        self.sensitivity_axes.set_ylabel("s(t)")
        self.sensitivity_axes.set_ylim(-1.15, 1.15)
        self.sensitivity_axes.grid(True, alpha=0.25)
        self.sensitivity_axes.legend(loc="best")

        self.transfer_axes.clear()
        self.transfer_axes.semilogx(
            frequencies,
            magnitude,
            color="#c43e36",
            linewidth=1.8,
            label="Finite-pulse |H_phi(f)|",
        )
        if self.show_instantaneous.get():
            instantaneous = instantaneous_pulse_magnitude(
                frequencies, parameters.bragg_order, parameters.free_time
            )
            self.transfer_axes.semilogx(
                frequencies,
                instantaneous,
                color="#555555",
                linestyle="--",
                linewidth=1.15,
                alpha=0.8,
                label="Instantaneous-pulse limit",
            )
        self.transfer_axes.set_title("Laser-Phase Transfer Function")
        self.transfer_axes.set_xlabel("Frequency (Hz)")
        self.transfer_axes.set_ylabel("|H_phi(f)|")
        self.transfer_axes.set_xlim(frequency_min, frequency_max)
        self.transfer_axes.set_ylim(bottom=0.0)
        self.transfer_axes.grid(True, which="both", alpha=0.25)
        self.transfer_axes.legend(loc="best")

        self.canvas.draw_idle()
        self.status_text.set(
            f"Total plotted sequence: {total_time * 1.0e3:.6g} ms\n"
            f"Peak effective pi/2 Rabi rate: {rate_half / (2.0 * np.pi):.6g} Hz\n"
            f"Peak effective pi Rabi rate: {rate_pi / (2.0 * np.pi):.6g} Hz\n"
            f"{timing_description}\n"
            f"{integration_description}\n"
            "DC check: H_phi(0) = 0"
        )

    def save_figure(self) -> None:
        output_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save figure",
            defaultextension=".png",
            filetypes=[
                ("PNG image", "*.png"),
                ("PDF document", "*.pdf"),
                ("SVG image", "*.svg"),
            ],
        )
        if not output_path:
            return
        try:
            self.figure.savefig(output_path, dpi=220, bbox_inches="tight")
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc), parent=self.root)


def _numerical_transfer_function(
    frequency_hz: np.ndarray, parameters: InterferometerParameters
) -> np.ndarray:
    """High-resolution quadrature used only by the self-test."""

    omega = 2.0 * np.pi * np.asarray(frequency_hz, dtype=float)
    pulse_specs = [
        (
            0.0,
            parameters.tau_pi_over_2,
            lambda local_t: parameters.omega_pi_over_2
            * np.cos(parameters.omega_pi_over_2 * local_t),
        ),
        (
            parameters.pulse_2_start,
            parameters.tau_pi,
            lambda local_t: -parameters.omega_pi
            * np.sin(parameters.omega_pi * local_t),
        ),
        (
            parameters.pulse_3_start,
            parameters.tau_pi_over_2,
            lambda local_t: parameters.omega_pi_over_2
            * np.sin(parameters.omega_pi_over_2 * local_t),
        ),
    ]
    result = np.zeros_like(omega, dtype=complex)
    for start, duration, derivative in pulse_specs:
        local_time = np.linspace(0.0, duration, 40_001)
        integrand = derivative(local_time)[None, :] * np.exp(
            -1.0j * omega[:, None] * (start + local_time[None, :])
        )
        result += np.trapz(integrand, local_time, axis=1)
    return parameters.bragg_order * result


def run_self_test() -> None:
    parameters = InterferometerParameters(
        bragg_order=3,
        tau_pi_over_2=37.0e-6,
        tau_pi=91.0e-6,
        free_time=0.247,
    )

    dc_value = transfer_function(np.array([0.0]), parameters)[0]
    if dc_value != 0.0j:
        raise AssertionError(f"DC response is not exactly zero: {dc_value}")

    boundary_times = np.array(
        [
            0.0,
            parameters.tau_pi_over_2,
            parameters.pulse_2_start,
            parameters.pulse_2_end,
            parameters.pulse_3_start,
            parameters.total_time,
        ]
    )
    expected = np.array([0.0, 1.0, 1.0, -1.0, -1.0, 0.0])
    actual = sensitivity_function(boundary_times, parameters)
    np.testing.assert_allclose(actual, expected, atol=2.0e-15, rtol=0.0)

    test_frequencies = np.array([0.37, 1.0, 17.0, 1234.5, 5789.0])
    analytic = transfer_function(test_frequencies, parameters)
    numerical = _numerical_transfer_function(test_frequencies, parameters)
    # The reference is a finite-grid trapezoidal integral, so its residual
    # discretization error is expected to be larger than floating-point error.
    np.testing.assert_allclose(analytic, numerical, rtol=1.0e-7, atol=5.0e-9)

    rabi_frequencies = np.array(
        [
            parameters.omega_pi_over_2 / (2.0 * np.pi),
            parameters.omega_pi / (2.0 * np.pi),
        ]
    )
    if not np.all(np.isfinite(transfer_function(rabi_frequencies, parameters))):
        raise AssertionError("Transfer function is not finite at a Rabi frequency.")

    first_order = InterferometerParameters(
        bragg_order=1,
        tau_pi_over_2=parameters.tau_pi_over_2,
        tau_pi=parameters.tau_pi,
        free_time=parameters.free_time,
    )
    np.testing.assert_allclose(
        analytic,
        parameters.bragg_order * transfer_function(test_frequencies, first_order),
        rtol=1.0e-14,
        atol=1.0e-14,
    )

    short_pulses = InterferometerParameters(
        bragg_order=2,
        tau_pi_over_2=1.0e-10,
        tau_pi=2.0e-10,
        free_time=0.31,
    )
    limit_frequencies = np.array([0.2, 1.7, 8.4])
    finite_magnitude = np.abs(transfer_function(limit_frequencies, short_pulses))
    ideal_magnitude = instantaneous_pulse_magnitude(
        limit_frequencies, short_pulses.bragg_order, short_pulses.free_time
    )
    np.testing.assert_allclose(
        finite_magnitude, ideal_magnitude, rtol=2.0e-8, atol=2.0e-8
    )

    gaussian_parameters = InterferometerParameters(
        bragg_order=3,
        tau_pi_over_2=42.0e-6,
        tau_pi=73.0e-6,
        free_time=0.19,
    )
    gaussian_schedule = _gaussian_schedule(gaussian_parameters)
    gaussian_boundaries = np.array(
        [
            gaussian_schedule[0][0],
            gaussian_schedule[0][1],
            gaussian_schedule[1][0],
            gaussian_schedule[1][1],
            gaussian_schedule[2][0],
            gaussian_schedule[2][1],
        ]
    )
    gaussian_expected = np.array([0.0, 1.0, 1.0, -1.0, -1.0, 0.0])
    np.testing.assert_allclose(
        gaussian_sensitivity_function(gaussian_boundaries, gaussian_parameters),
        gaussian_expected,
        rtol=0.0,
        atol=2.0e-15,
    )

    nodes, weights = np.polynomial.legendre.leggauss(512)
    pulse_changes = []
    for pulse_index, (start, end, _center, sigma, area) in enumerate(
        gaussian_schedule
    ):
        half_window = 0.5 * (end - start)
        local_time = half_window * nodes
        rabi, accumulated = _gaussian_rabi_and_area(local_time, sigma, area)
        if pulse_index == 0:
            derivative = rabi * np.cos(accumulated)
        elif pulse_index == 1:
            derivative = -rabi * np.sin(accumulated)
        else:
            derivative = rabi * np.sin(accumulated)
        pulse_changes.append(half_window * np.dot(weights, derivative))
    np.testing.assert_allclose(
        pulse_changes, [1.0, -2.0, 1.0], rtol=2.0e-13, atol=2.0e-13
    )

    gaussian_response = gaussian_transfer_function(
        test_frequencies, gaussian_parameters
    )
    gaussian_first_order = InterferometerParameters(
        bragg_order=1,
        tau_pi_over_2=gaussian_parameters.tau_pi_over_2,
        tau_pi=gaussian_parameters.tau_pi,
        free_time=gaussian_parameters.free_time,
    )
    np.testing.assert_allclose(
        gaussian_response,
        gaussian_parameters.bragg_order
        * gaussian_transfer_function(test_frequencies, gaussian_first_order),
        rtol=1.0e-13,
        atol=1.0e-13,
    )

    short_gaussian = InterferometerParameters(
        bragg_order=2,
        tau_pi_over_2=1.0e-10,
        tau_pi=2.0e-10,
        free_time=0.31,
    )
    gaussian_limit_magnitude = np.abs(
        gaussian_transfer_function(limit_frequencies, short_gaussian)
    )
    gaussian_ideal_magnitude = instantaneous_pulse_magnitude(
        limit_frequencies, short_gaussian.bragg_order, short_gaussian.free_time
    )
    np.testing.assert_allclose(
        gaussian_limit_magnitude,
        gaussian_ideal_magnitude,
        rtol=2.0e-8,
        atol=2.0e-8,
    )

    print("All self-tests passed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finite-pulse Bragg transfer-function calculator"
    )
    parser.add_argument(
        "--self-test", action="store_true", help="run validation tests and exit"
    )
    arguments = parser.parse_args()
    if arguments.self_test:
        run_self_test()
        return

    root = tk.Tk()
    BraggTransferFunctionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
