"""Retroreflected Bragg transfer functions with finite propagation delay.

This is a propagation-aware companion to ``bragg_transfer_function_ui.py``.
The user supplies the square durations or Gaussian intensity FWHM values in
microseconds.  The nominal peak two-photon Rabi rates are derived from the
target pulse areas.  A pulse envelope at the atoms is combined with a copy
delayed by 2 L / c, so that

    Omega_raw(t) = Omega_input * sqrt(I(t) I(t-delay)) / I_peak.

Model A rescales each overlap envelope to the ideal pi/2-pi-pi/2 areas.
Model B keeps the overlap loss and evaluates the sensitivity function from an
effective resonant two-level propagator.  The Bragg order remains an external
phase-gain factor; a full high-order momentum-state calculation is outside the
scope of this reduced model.
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


C_LIGHT = 299_792_458.0
GAUSSIAN_TRUNCATION_SIGMA = 6.0
TARGET_AREAS = (0.5 * np.pi, np.pi, 0.5 * np.pi)
BASE_PHASES = (0.0, 0.0, 0.5 * np.pi)


@dataclass(frozen=True)
class PropagationParameters:
    bragg_order: int
    omega_pi_over_2: float
    omega_pi: float
    center_separation: float
    distance_to_mirror: float
    pulse_shape: str
    model: str

    def validate(self) -> None:
        numeric = (
            self.omega_pi_over_2,
            self.omega_pi,
            self.center_separation,
            self.distance_to_mirror,
        )
        if self.bragg_order < 1:
            raise ValueError("Bragg order must be a positive integer.")
        if not np.all(np.isfinite(numeric)):
            raise ValueError("Rabi rates, T and L must be finite.")
        if self.omega_pi_over_2 <= 0.0 or self.omega_pi <= 0.0:
            raise ValueError("Both input Rabi rates must be positive.")
        if self.center_separation <= 0.0:
            raise ValueError("Pulse-center separation T must be positive.")
        if self.distance_to_mirror < 0.0:
            raise ValueError("Distance L cannot be negative.")
        if self.pulse_shape not in {"Square", "Gaussian"}:
            raise ValueError("Unsupported pulse shape.")
        if self.model not in {"A: area compensated", "B: fixed input"}:
            raise ValueError("Unsupported propagation model.")

    @property
    def delay(self) -> float:
        return 2.0 * self.distance_to_mirror / C_LIGHT


@dataclass(frozen=True)
class EffectivePulse:
    target_area: float
    input_omega: float
    command_center: float
    effective_center: float
    start: float
    end: float
    width_parameter: float
    raw_peak_omega: float
    effective_peak_omega: float
    raw_area: float
    effective_area: float
    area_scale: float
    pulse_shape: str

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def nominal_width(self) -> float:
        """Square command duration or Gaussian intensity FWHM."""

        if self.pulse_shape == "Square":
            return self.target_area / self.input_omega
        sigma = self.width_parameter
        return 2.0 * np.sqrt(2.0 * np.log(2.0)) * sigma

    def omega(self, time_s: np.ndarray | float) -> np.ndarray:
        t = np.asarray(time_s, dtype=float)
        value = np.zeros_like(t)
        mask = (t >= self.start) & (t <= self.end)
        if self.pulse_shape == "Square":
            value[mask] = self.effective_peak_omega
        else:
            local = t[mask] - self.effective_center
            value[mask] = self.effective_peak_omega * np.exp(
                -0.5 * (local / self.width_parameter) ** 2
            )
        return value

    def accumulated_area(self, time_s: np.ndarray | float) -> np.ndarray:
        t = np.asarray(time_s, dtype=float)
        clipped = np.clip(t, self.start, self.end)
        if self.pulse_shape == "Square":
            area = self.effective_peak_omega * (clipped - self.start)
        else:
            sigma = self.width_parameter
            lower = (self.start - self.effective_center) / (np.sqrt(2.0) * sigma)
            upper = (clipped - self.effective_center) / (np.sqrt(2.0) * sigma)
            erf_upper = _erf_array(upper)
            area = (
                self.effective_peak_omega
                * sigma
                * np.sqrt(np.pi / 2.0)
                * (erf_upper - math.erf(lower))
            )
        return np.where(t <= self.start, 0.0, np.where(t >= self.end, self.effective_area, area))


def _erf_array(values: np.ndarray) -> np.ndarray:
    flat = np.asarray(values, dtype=float).ravel()
    result = np.fromiter((math.erf(float(value)) for value in flat), dtype=float)
    return result.reshape(np.shape(values))


def _complex_exponential_integral(q: np.ndarray, duration: float) -> np.ndarray:
    """Return integral_0^duration exp(i q t) dt stably."""

    return duration * np.exp(0.5j * q * duration) * np.sinc(
        q * duration / (2.0 * np.pi)
    )


def _nominal_width_parameter(shape: str, omega: float, target_area: float) -> float:
    if shape == "Square":
        return target_area / omega
    edge_erf = math.erf(GAUSSIAN_TRUNCATION_SIGMA / np.sqrt(2.0))
    return target_area / (omega * np.sqrt(2.0 * np.pi) * edge_erf)


def _input_omega_from_width(shape: str, nominal_width: float, target_area: float) -> float:
    """Convert square duration or Gaussian intensity FWHM to peak Rabi rate."""

    if not np.isfinite(nominal_width) or nominal_width <= 0.0:
        raise ValueError("Both pulse widths must be positive and finite.")
    if shape == "Square":
        return target_area / nominal_width
    sigma = nominal_width / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    edge_erf = math.erf(GAUSSIAN_TRUNCATION_SIGMA / np.sqrt(2.0))
    return target_area / (sigma * np.sqrt(2.0 * np.pi) * edge_erf)


def _make_effective_pulse(
    shape: str,
    model: str,
    input_omega: float,
    target_area: float,
    command_center: float,
    delay: float,
) -> EffectivePulse:
    width = _nominal_width_parameter(shape, input_omega, target_area)
    effective_center = command_center + 0.5 * delay

    if shape == "Square":
        command_duration = width
        overlap_duration = command_duration - delay
        if overlap_duration <= 0.0:
            raise ValueError(
                "The propagation delay is at least as long as a square input pulse; "
                "the two counter-propagating envelopes do not overlap."
            )
        start = effective_center - 0.5 * overlap_duration
        end = effective_center + 0.5 * overlap_duration
        raw_peak = input_omega
        raw_area = raw_peak * overlap_duration
    else:
        sigma = width
        overlap_half_width = GAUSSIAN_TRUNCATION_SIGMA * sigma - 0.5 * delay
        if overlap_half_width <= 0.0:
            raise ValueError(
                "The propagation delay separates the truncated Gaussian envelopes; "
                "increase the Rabi pulse duration or reduce L."
            )
        start = effective_center - overlap_half_width
        end = effective_center + overlap_half_width
        raw_peak = input_omega * np.exp(-delay**2 / (8.0 * sigma**2))
        edge = overlap_half_width / (np.sqrt(2.0) * sigma)
        raw_area = raw_peak * sigma * np.sqrt(2.0 * np.pi) * math.erf(edge)

    if model == "A: area compensated":
        area_scale = target_area / raw_area
        effective_area = target_area
    else:
        area_scale = 1.0
        effective_area = raw_area

    return EffectivePulse(
        target_area=target_area,
        input_omega=input_omega,
        command_center=command_center,
        effective_center=effective_center,
        start=start,
        end=end,
        width_parameter=width,
        raw_peak_omega=raw_peak,
        effective_peak_omega=raw_peak * area_scale,
        raw_area=raw_area,
        effective_area=effective_area,
        area_scale=area_scale,
        pulse_shape=shape,
    )


def build_schedule(parameters: PropagationParameters) -> list[EffectivePulse]:
    parameters.validate()
    centers = (0.0, parameters.center_separation, 2.0 * parameters.center_separation)
    rates = (parameters.omega_pi_over_2, parameters.omega_pi, parameters.omega_pi_over_2)
    pulses = [
        _make_effective_pulse(
            parameters.pulse_shape,
            parameters.model,
            rate,
            area,
            center,
            parameters.delay,
        )
        for rate, area, center in zip(rates, TARGET_AREAS, centers)
    ]
    if pulses[0].end > pulses[1].start or pulses[1].end > pulses[2].start:
        raise ValueError(
            "Effective pulse windows overlap. Increase T or use a Hamiltonian model "
            "that includes simultaneous pulses."
        )
    return pulses


def _rotation(area: float, phase: float) -> np.ndarray:
    cosine = np.cos(0.5 * area)
    sine = np.sin(0.5 * area)
    return np.array(
        [
            [cosine, -1.0j * np.exp(-1.0j * phase) * sine],
            [-1.0j * np.exp(1.0j * phase) * sine, cosine],
        ],
        dtype=complex,
    )


def _transition_probability(
    pulses: list[EffectivePulse],
    phases: tuple[float, float, float],
    step_time: float | None = None,
    step_size: float = 0.0,
) -> float:
    state = np.array([1.0 + 0.0j, 0.0 + 0.0j])
    for pulse, phase in zip(pulses, phases):
        if step_time is None:
            operator = _rotation(pulse.effective_area, phase)
        else:
            before = float(pulse.accumulated_area(np.array([step_time]))[0])
            after = pulse.effective_area - before
            operator = _rotation(after, phase + step_size) @ _rotation(before, phase)
        state = operator @ state
    return float(np.abs(state[1]) ** 2)


def _fringe_slope(pulses: list[EffectivePulse], epsilon: float = 1.0e-6) -> float:
    plus = _transition_probability(
        pulses, (BASE_PHASES[0], BASE_PHASES[1], BASE_PHASES[2] + epsilon)
    )
    minus = _transition_probability(
        pulses, (BASE_PHASES[0], BASE_PHASES[1], BASE_PHASES[2] - epsilon)
    )
    slope = (plus - minus) / (2.0 * epsilon)
    if abs(slope) < 1.0e-8:
        raise ValueError(
            "Model B has nearly zero mid-fringe slope for these pulse areas; "
            "the inferred phase sensitivity is ill-conditioned."
        )
    return slope


def sensitivity_function(
    time_s: np.ndarray | float,
    parameters: PropagationParameters,
    pulses: list[EffectivePulse] | None = None,
) -> np.ndarray:
    """Sensitivity to a local Bragg-phase step, normalized to output phase."""

    schedule = build_schedule(parameters) if pulses is None else pulses
    t = np.asarray(time_s, dtype=float)
    result = np.zeros_like(t)
    inside = (t > schedule[0].start) & (t < schedule[-1].end)
    if not np.any(inside):
        return result

    slope = _fringe_slope(schedule)
    epsilon = 1.0e-6
    flat_result = result.ravel()
    flat_time = t.ravel()
    flat_inside = inside.ravel()
    for index in np.flatnonzero(flat_inside):
        time_value = float(flat_time[index])
        plus = _transition_probability(
            schedule, BASE_PHASES, time_value, epsilon
        )
        minus = _transition_probability(
            schedule, BASE_PHASES, time_value, -epsilon
        )
        derivative = (plus - minus) / (2.0 * epsilon)
        # This sign gives the MIGA/manual convention: first plateau +1.
        flat_result[index] = -derivative / slope
    return result


def _weighted_fourier_sum(
    omega: np.ndarray,
    time_nodes: np.ndarray,
    weighted_values: np.ndarray,
) -> np.ndarray:
    result = np.empty(omega.size, dtype=complex)
    chunk_size = 1024
    for start in range(0, omega.size, chunk_size):
        stop = min(start + chunk_size, omega.size)
        phase = np.exp(-1.0j * omega[start:stop, None] * time_nodes[None, :])
        result[start:stop] = phase @ weighted_values
    return result


def atom_phase_transfer_function(
    frequency_hz: np.ndarray | float,
    parameters: PropagationParameters,
    pulses: list[EffectivePulse] | None = None,
) -> np.ndarray:
    """Return H_AI = n F[ds/dt] for the delayed effective pulses."""

    schedule = build_schedule(parameters) if pulses is None else pulses
    frequency = np.asarray(frequency_hz, dtype=float)
    original_shape = frequency.shape
    flat_frequency = frequency.ravel()
    omega = 2.0 * np.pi * flat_frequency
    maximum_frequency = float(np.max(np.abs(flat_frequency))) if flat_frequency.size else 0.0
    g_transform = np.zeros(flat_frequency.size, dtype=complex)

    # Pulses require numerical quadrature; long free intervals are integrated exactly.
    for pulse in schedule:
        order = max(256, int(np.ceil(20.0 * maximum_frequency * pulse.duration)) + 64)
        if order > 4096:
            raise ValueError(
                "The requested frequency and pulse duration require more than 4096 "
                "quadrature nodes. Reduce f_max or the pulse duration."
            )
        nodes, weights = np.polynomial.legendre.leggauss(order)
        half_window = 0.5 * pulse.duration
        time_nodes = pulse.effective_center + half_window * nodes
        quadrature_weights = half_window * weights
        g_values = sensitivity_function(time_nodes, parameters, schedule)
        g_transform += _weighted_fourier_sum(
            omega, time_nodes, quadrature_weights * g_values
        )

    for left, right in ((schedule[0].end, schedule[1].start), (schedule[1].end, schedule[2].start)):
        if right <= left:
            continue
        midpoint = 0.5 * (left + right)
        plateau = float(sensitivity_function(np.array([midpoint]), parameters, schedule)[0])
        duration = right - left
        g_transform += (
            plateau
            * np.exp(-1.0j * omega * left)
            * _complex_exponential_integral(-omega, duration)
        )

    response = parameters.bragg_order * (1.0j * omega) * g_transform
    response = np.where(omega == 0.0, 0.0 + 0.0j, response)
    return response.reshape(original_shape)


def delay_phase_transfer(
    frequency_hz: np.ndarray | float, delay: float
) -> np.ndarray:
    frequency = np.asarray(frequency_hz, dtype=float)
    omega = 2.0 * np.pi * frequency
    return 1.0 - np.exp(-1.0j * omega * delay)


def source_phase_transfer_function(
    frequency_hz: np.ndarray | float,
    atom_response: np.ndarray,
    delay: float,
) -> np.ndarray:
    return atom_response * delay_phase_transfer(frequency_hz, delay)


def frequency_noise_transfer_function(
    frequency_hz: np.ndarray | float,
    source_phase_response: np.ndarray,
) -> np.ndarray:
    """Map laser frequency noise in Hz to atom phase in rad."""

    frequency = np.asarray(frequency_hz, dtype=float)
    return np.divide(
        source_phase_response,
        1.0j * frequency,
        out=np.zeros_like(source_phase_response, dtype=complex),
        where=frequency != 0.0,
    )


def _plot_time_grid(pulses: list[EffectivePulse]) -> np.ndarray:
    segments: list[np.ndarray] = []
    padding = max(0.04 * (pulses[-1].end - pulses[0].start), 0.2 * pulses[0].duration)
    segments.append(np.linspace(pulses[0].start - padding, pulses[0].start, 25, endpoint=False))
    for index, pulse in enumerate(pulses):
        segments.append(np.linspace(pulse.start, pulse.end, 260, endpoint=False))
        if index < len(pulses) - 1:
            segments.append(np.linspace(pulse.end, pulses[index + 1].start, 80, endpoint=False))
    segments.append(np.linspace(pulses[-1].end, pulses[-1].end + padding, 25))
    return np.unique(np.concatenate(segments))


def _local_input_intensity(
    local_time: np.ndarray, pulse: EffectivePulse, delay: float
) -> tuple[np.ndarray, np.ndarray]:
    if pulse.pulse_shape == "Square":
        duration = pulse.nominal_width
        forward = (np.abs(local_time) <= 0.5 * duration).astype(float)
        reflected = (np.abs(local_time - delay) <= 0.5 * duration).astype(float)
    else:
        sigma = pulse.width_parameter
        forward = np.exp(-0.5 * (local_time / sigma) ** 2)
        reflected = np.exp(-0.5 * ((local_time - delay) / sigma) ** 2)
        forward[np.abs(local_time) > GAUSSIAN_TRUNCATION_SIGMA * sigma] = 0.0
        reflected[np.abs(local_time - delay) > GAUSSIAN_TRUNCATION_SIGMA * sigma] = 0.0
    return forward, reflected


class PropagationTransferApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Propagation-Aware Bragg Transfer Function")
        self.root.geometry("1500x980")
        self.root.minsize(1180, 780)

        self.pulse_shape = tk.StringVar(value="Square")
        self.model = tk.StringVar(value="A: area compensated")
        self.bragg_order = tk.StringVar(value="1")
        self.tau_half_us = tk.StringVar(value="25")
        self.tau_pi_us = tk.StringVar(value="50")
        self.center_separation_ms = tk.StringVar(value="250")
        self.distance_m = tk.StringVar(value="200")
        self.frequency_min_hz = tk.StringVar(value="0.1")
        self.frequency_max_hz = tk.StringVar(value="100000")
        self.frequency_points = tk.StringVar(value="2500")
        self.status_text = tk.StringVar(value="Ready")

        self._configure_style()
        self._build_layout()
        self.calculate()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 15, "bold"))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Status.TLabel", foreground="#304860")

    def _build_layout(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        controls = ttk.Frame(self.root, padding=(12, 12, 10, 12))
        controls.grid(row=0, column=0, sticky="ns")
        controls.columnconfigure(0, weight=1)

        ttk.Label(controls, text="Propagation-Aware Bragg", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        ttk.Label(
            controls,
            text="Retroreflection delay: 2L/c\nEffective resonant two-level model",
            foreground="#536878",
        ).grid(row=1, column=0, sticky="w", pady=(0, 12))

        pulse_box = ttk.LabelFrame(
            controls, text="Pulse and propagation", style="Section.TLabelframe", padding=9
        )
        pulse_box.grid(row=2, column=0, sticky="ew", pady=(0, 9))
        pulse_box.columnconfigure(1, weight=1)
        self._add_selector(pulse_box, 0, "Pulse shape", self.pulse_shape, ("Square", "Gaussian"))
        self._add_selector(
            pulse_box,
            1,
            "Propagation model",
            self.model,
            ("A: area compensated", "B: fixed input"),
        )
        self._add_entry(pulse_box, 2, "Bragg order n", self.bragg_order, "integer")
        self._add_entry(
            pulse_box, 3, "pi/2 duration / FWHM", self.tau_half_us, "us"
        )
        self._add_entry(pulse_box, 4, "pi duration / FWHM", self.tau_pi_us, "us")
        self._add_entry(pulse_box, 5, "Center separation T", self.center_separation_ms, "ms")
        self._add_entry(pulse_box, 6, "Atom-mirror distance L", self.distance_m, "m")

        frequency_box = ttk.LabelFrame(
            controls, text="Frequency grid", style="Section.TLabelframe", padding=9
        )
        frequency_box.grid(row=3, column=0, sticky="ew", pady=(0, 9))
        self._add_entry(frequency_box, 0, "Minimum frequency", self.frequency_min_hz, "Hz")
        self._add_entry(frequency_box, 1, "Maximum frequency", self.frequency_max_hz, "Hz")
        self._add_entry(frequency_box, 2, "Frequency points", self.frequency_points, "integer")

        button_row = ttk.Frame(controls)
        button_row.grid(row=4, column=0, sticky="ew")
        button_row.columnconfigure((0, 1), weight=1)
        ttk.Button(button_row, text="Calculate", command=self.calculate).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(button_row, text="Save figure...", command=self.save_figure).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        ttk.Separator(controls).grid(row=5, column=0, sticky="ew", pady=12)
        ttk.Label(
            controls,
            textvariable=self.status_text,
            style="Status.TLabel",
            justify="left",
            wraplength=305,
        ).grid(row=6, column=0, sticky="nw")
        controls.rowconfigure(6, weight=1)

        plot_frame = ttk.Frame(self.root, padding=(0, 8, 10, 8))
        plot_frame.grid(row=0, column=1, sticky="nsew")
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)
        self.figure = Figure(figsize=(12.0, 9.2), dpi=100, constrained_layout=True)
        axes = self.figure.subplots(3, 2)
        self.envelope_axes = axes[0, 0]
        self.sensitivity_axes = axes[0, 1]
        self.atom_axes = axes[1, 0]
        self.delay_axes = axes[1, 1]
        self.total_phase_axes = axes[2, 0]
        self.frequency_noise_axes = axes[2, 1]
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame, pack_toolbar=False)
        toolbar.update()
        toolbar.grid(row=1, column=0, sticky="ew")
        self.root.bind("<Return>", lambda _event: self.calculate())

    @staticmethod
    def _add_entry(parent, row, label, variable, unit) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable, width=13).grid(
            row=row, column=1, sticky="ew", padx=(8, 5), pady=3
        )
        ttk.Label(parent, text=unit, foreground="#606060").grid(
            row=row, column=2, sticky="w", pady=3
        )

    def _add_selector(self, parent, row, label, variable, values) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        selector = ttk.Combobox(
            parent, textvariable=variable, values=values, state="readonly", width=19
        )
        selector.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=3)
        selector.bind("<<ComboboxSelected>>", lambda _event: self.calculate())

    def _read_inputs(self):
        try:
            order_float = float(self.bragg_order.get())
            width_half = float(self.tau_half_us.get()) * 1.0e-6
            width_pi = float(self.tau_pi_us.get()) * 1.0e-6
            center_separation = float(self.center_separation_ms.get()) * 1.0e-3
            distance = float(self.distance_m.get())
            f_min = float(self.frequency_min_hz.get())
            f_max = float(self.frequency_max_hz.get())
            point_float = float(self.frequency_points.get())
        except ValueError as exc:
            raise ValueError("All fields must contain valid numbers.") from exc
        if not order_float.is_integer() or not point_float.is_integer():
            raise ValueError("Bragg order and frequency points must be integers.")
        pulse_shape = self.pulse_shape.get()
        omega_half = _input_omega_from_width(
            pulse_shape, width_half, TARGET_AREAS[0]
        )
        omega_pi = _input_omega_from_width(pulse_shape, width_pi, TARGET_AREAS[1])
        parameters = PropagationParameters(
            bragg_order=int(order_float),
            omega_pi_over_2=omega_half,
            omega_pi=omega_pi,
            center_separation=center_separation,
            distance_to_mirror=distance,
            pulse_shape=pulse_shape,
            model=self.model.get(),
        )
        parameters.validate()
        points = int(point_float)
        if not (np.isfinite(f_min) and np.isfinite(f_max)) or f_min <= 0.0 or f_max <= f_min:
            raise ValueError("Use finite frequency limits with 0 < f_min < f_max.")
        if not 100 <= points <= 100_000:
            raise ValueError("Frequency points must be between 100 and 100000.")
        return parameters, f_min, f_max, points

    def calculate(self) -> None:
        try:
            parameters, f_min, f_max, points = self._read_inputs()
            pulses = build_schedule(parameters)
            frequencies = np.geomspace(f_min, f_max, points)
            atom_response = atom_phase_transfer_function(frequencies, parameters, pulses)
            delay_response = delay_phase_transfer(frequencies, parameters.delay)
            total_phase_response = source_phase_transfer_function(
                frequencies, atom_response, parameters.delay
            )
            frequency_response = frequency_noise_transfer_function(
                frequencies, total_phase_response
            )
            time = _plot_time_grid(pulses)
            sensitivity = sensitivity_function(time, parameters, pulses)
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc), parent=self.root)
            return

        representative = pulses[0]
        half_span = max(
            0.7 * representative.nominal_width + parameters.delay,
            0.65 * representative.duration,
        )
        local_time = np.linspace(-half_span, half_span, 700)
        forward, reflected = _local_input_intensity(local_time, representative, parameters.delay)
        effective = representative.omega(local_time + representative.command_center)
        effective_normalized = effective / max(representative.effective_peak_omega, 1.0e-300)

        self.envelope_axes.clear()
        self.envelope_axes.plot(local_time * 1.0e6, forward, label="Forward intensity I(t)")
        self.envelope_axes.plot(
            local_time * 1.0e6, reflected, label="Reflected I(t-delay)", linestyle="--"
        )
        self.envelope_axes.plot(
            local_time * 1.0e6,
            effective_normalized,
            label="Normalized effective Rabi",
            linewidth=2.0,
        )
        self.envelope_axes.set_title("pi/2 Pulse Overlap at the Atoms")
        self.envelope_axes.set_xlabel("Time relative to commanded center (us)")
        self.envelope_axes.set_ylabel("Normalized envelope")
        self.envelope_axes.grid(True, alpha=0.25)
        self.envelope_axes.legend(fontsize=8)

        self.sensitivity_axes.clear()
        self.sensitivity_axes.plot(time * 1.0e3, sensitivity, color="#1769aa", linewidth=1.8)
        for pulse in pulses:
            self.sensitivity_axes.axvspan(
                pulse.start * 1.0e3, pulse.end * 1.0e3, color="#ffb74d", alpha=0.2
            )
        self.sensitivity_axes.axhline(0.0, color="#333333", linewidth=0.8)
        self.sensitivity_axes.set_title(f"Sensitivity Function - Model {parameters.model[0]}")
        self.sensitivity_axes.set_xlabel("Time (ms)")
        self.sensitivity_axes.set_ylabel("s(t)")
        limit = max(1.15, 1.08 * float(np.max(np.abs(sensitivity))))
        self.sensitivity_axes.set_ylim(-limit, limit)
        self.sensitivity_axes.grid(True, alpha=0.25)

        self.atom_axes.clear()
        self.atom_axes.loglog(frequencies, np.abs(atom_response), color="#c43e36")
        self.atom_axes.set_title("Atomic Local-Phase Transfer")
        self.atom_axes.set_xlabel("Frequency (Hz)")
        self.atom_axes.set_ylabel("|H_AI|  (rad/rad)")
        self.atom_axes.grid(True, which="both", alpha=0.25)

        self.delay_axes.clear()
        self.delay_axes.loglog(frequencies, np.abs(delay_response), color="#6a5acd")
        self.delay_axes.set_title("Propagation Phase-Difference Filter")
        self.delay_axes.set_xlabel("Frequency (Hz)")
        self.delay_axes.set_ylabel("|1 - exp(-i omega delay)|")
        self.delay_axes.grid(True, which="both", alpha=0.25)

        self.total_phase_axes.clear()
        self.total_phase_axes.loglog(
            frequencies, np.abs(atom_response), color="#c43e36", alpha=0.55, label="|H_AI|"
        )
        self.total_phase_axes.loglog(
            frequencies,
            np.abs(delay_response),
            color="#6a5acd",
            alpha=0.65,
            label="|D_delay|",
        )
        self.total_phase_axes.loglog(
            frequencies,
            np.abs(total_phase_response),
            color="#00897b",
            linewidth=1.8,
            label="|H_AI D_delay|",
        )
        self.total_phase_axes.set_title("Combined Source-Phase Transfer")
        self.total_phase_axes.set_xlabel("Frequency (Hz)")
        self.total_phase_axes.set_ylabel("Magnitude (rad/rad)")
        self.total_phase_axes.grid(True, which="both", alpha=0.25)
        self.total_phase_axes.legend(fontsize=8)

        self.frequency_noise_axes.clear()
        self.frequency_noise_axes.loglog(
            frequencies, np.abs(frequency_response), color="#d17b0f", linewidth=1.8
        )
        self.frequency_noise_axes.set_title("Laser-Frequency-Noise Transfer")
        self.frequency_noise_axes.set_xlabel("Frequency (Hz)")
        self.frequency_noise_axes.set_ylabel("|H_nu|  (rad/Hz)")
        self.frequency_noise_axes.grid(True, which="both", alpha=0.25)

        self.canvas.draw_idle()
        widths = [pulse.nominal_width * 1.0e6 for pulse in pulses[:2]]
        area_ratios = [pulse.raw_area / pulse.target_area for pulse in pulses[:2]]
        scale_factors = [pulse.area_scale for pulse in pulses[:2]]
        self.status_text.set(
            f"Round-trip delay 2L/c: {parameters.delay * 1.0e6:.6g} us\n"
            f"Nominal pi/2 width/FWHM: {widths[0]:.6g} us\n"
            f"Nominal pi width/FWHM: {widths[1]:.6g} us\n"
            f"Raw area ratios (pi/2, pi): {area_ratios[0]:.8g}, {area_ratios[1]:.8g}\n"
            f"Applied area scales: {scale_factors[0]:.8g}, {scale_factors[1]:.8g}\n"
            f"Effective peak rates: {pulses[0].effective_peak_omega/(2*np.pi)/1e3:.6g}, "
            f"{pulses[1].effective_peak_omega/(2*np.pi)/1e3:.6g} kHz\n"
            "T is center-to-center for both pulse shapes.\n"
            "H_total_phase = H_AI (1-exp(-i omega 2L/c)).\n"
            "H_nu maps frequency noise in Hz to atom phase."
        )

    def save_figure(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save figure",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("PDF document", "*.pdf"), ("SVG image", "*.svg")],
        )
        if not path:
            return
        try:
            self.figure.savefig(path, dpi=220, bbox_inches="tight")
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc), parent=self.root)


def run_self_test() -> None:
    base = dict(
        bragg_order=1,
        omega_pi_over_2=2.0 * np.pi * 10.0e3,
        omega_pi=2.0 * np.pi * 10.0e3,
        center_separation=0.25,
        pulse_shape="Square",
    )
    zero_a = PropagationParameters(
        **base, distance_to_mirror=0.0, model="A: area compensated"
    )
    zero_b = PropagationParameters(
        **base, distance_to_mirror=0.0, model="B: fixed input"
    )
    pulses_a = build_schedule(zero_a)
    pulses_b = build_schedule(zero_b)
    np.testing.assert_allclose(
        [pulse.effective_area for pulse in pulses_a], TARGET_AREAS, atol=2e-15, rtol=0
    )
    np.testing.assert_allclose(
        [pulse.effective_area for pulse in pulses_b], TARGET_AREAS, atol=2e-15, rtol=0
    )
    probe_times = np.array(
        [
            0.5 * (pulses_a[0].end + pulses_a[1].start),
            0.5 * (pulses_a[1].end + pulses_a[2].start),
        ]
    )
    np.testing.assert_allclose(
        sensitivity_function(probe_times, zero_a, pulses_a), [1.0, -1.0], atol=2e-9
    )
    np.testing.assert_allclose(
        sensitivity_function(probe_times, zero_b, pulses_b), [1.0, -1.0], atol=2e-9
    )

    distance = 200.0
    delayed_b = PropagationParameters(
        **base, distance_to_mirror=distance, model="B: fixed input"
    )
    delayed_pulses = build_schedule(delayed_b)
    delay = delayed_b.delay
    expected_half_ratio = 1.0 - delay / delayed_pulses[0].nominal_width
    expected_pi_ratio = 1.0 - delay / delayed_pulses[1].nominal_width
    np.testing.assert_allclose(
        [
            delayed_pulses[0].raw_area / delayed_pulses[0].target_area,
            delayed_pulses[1].raw_area / delayed_pulses[1].target_area,
        ],
        [expected_half_ratio, expected_pi_ratio],
        atol=2e-15,
        rtol=2e-15,
    )

    gaussian_b = PropagationParameters(
        **{**base, "pulse_shape": "Gaussian"},
        distance_to_mirror=distance,
        model="B: fixed input",
    )
    gaussian_pulses = build_schedule(gaussian_b)
    sigma = gaussian_pulses[0].width_parameter
    edge = GAUSSIAN_TRUNCATION_SIGMA - gaussian_b.delay / (2.0 * sigma)
    expected_gaussian_ratio = (
        np.exp(-gaussian_b.delay**2 / (8.0 * sigma**2))
        * math.erf(edge / np.sqrt(2.0))
        / math.erf(GAUSSIAN_TRUNCATION_SIGMA / np.sqrt(2.0))
    )
    np.testing.assert_allclose(
        gaussian_pulses[0].raw_area / gaussian_pulses[0].target_area,
        expected_gaussian_ratio,
        rtol=2e-14,
        atol=2e-14,
    )

    frequencies = np.array([0.3, 3.7, 97.0, 4100.0])
    response_a = atom_phase_transfer_function(frequencies, zero_a, pulses_a)
    response_b = atom_phase_transfer_function(frequencies, zero_b, pulses_b)
    np.testing.assert_allclose(response_a, response_b, rtol=2e-8, atol=2e-9)
    delay_filter = delay_phase_transfer(frequencies, delay)
    np.testing.assert_allclose(
        np.abs(delay_filter),
        2.0 * np.abs(np.sin(np.pi * frequencies * delay)),
        rtol=2e-14,
        atol=2e-14,
    )
    print("All propagation-aware self-tests passed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Propagation-aware finite-pulse Bragg transfer calculator"
    )
    parser.add_argument("--self-test", action="store_true", help="run validation tests and exit")
    args = parser.parse_args()
    if args.self_test:
        run_self_test()
        return
    root = tk.Tk()
    PropagationTransferApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
