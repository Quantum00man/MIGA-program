from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib as mpl
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


K_B = 1.380649e-23
AMU = 1.66053906660e-27
DEFAULT_SPECIES = "87Rb"
SPECIES_MASS_AMU = {
    "87Rb": 86.909180527,
    "133Cs": 132.90545196,
    "39K": 38.9637064864,
    "23Na": 22.9897692820,
    "4He": 4.00260325413,
    "Custom": 86.909180527,
}

mpl.rcParams.update(
    {
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "figure.dpi": 110,
        "axes.grid": False,
    }
)


@dataclass
class PhysicsParameters:
    species: str
    atomic_mass_amu: float
    temperature_uK: float
    launch_velocity_m_s: float
    detector_z_m: float
    probe_sigma_m: float
    gravity_m_s2: float
    show_return_pass: bool
    t_max_s: float
    time_points: int
    velocity_points: int


@dataclass
class ElectronicsParameters:
    enable_filter: bool
    cutoff_hz: float
    poles: int


@dataclass
class PeakMetrics:
    label: str
    ideal_time_ms: float | None
    filtered_time_ms: float | None
    delay_ms: float | None
    ideal_peak: float | None
    filtered_peak: float | None
    attenuation_pct: float | None
    ideal_fwhm_ms: float | None
    filtered_fwhm_ms: float | None
    broadening_ms: float | None


@dataclass
class GaussianFit:
    label: str
    amplitude: float
    center_ms: float
    sigma_ms: float
    fwhm_ms: float
    rmse: float
    r_squared: float
    fit_curve: np.ndarray


@dataclass
class SimulationResult:
    time_s: np.ndarray
    velocity_grid_m_s: np.ndarray
    velocity_pdf: np.ndarray
    z_mean_m: np.ndarray
    z_rms_m: np.ndarray
    ideal_signal: np.ndarray
    filtered_signal: np.ndarray
    signal_difference: np.ndarray
    sigma_v_m_s: float
    upward_crossing_ms: float | None
    downward_crossing_ms: float | None
    apex_time_ms: float
    frequency_hz: np.ndarray
    magnitude_db: np.ndarray
    phase_deg: np.ndarray
    upward_metrics: PeakMetrics | None
    downward_metrics: PeakMetrics | None
    upward_gaussian_fit: GaussianFit | None
    downward_gaussian_fit: GaussianFit | None


def thermal_sigma_v(temperature_uK: float, atomic_mass_amu: float) -> float:
    temperature_k = temperature_uK * 1e-6
    mass_kg = atomic_mass_amu * AMU
    if temperature_k < 0:
        raise ValueError("Temperature must be non-negative.")
    if mass_kg <= 0:
        raise ValueError("Atomic mass must be positive.")
    return math.sqrt(K_B * temperature_k / mass_kg)


def gaussian_pdf(x: np.ndarray, mean: float, sigma: float) -> np.ndarray:
    sigma_eff = max(sigma, 1e-8)
    norm = 1.0 / (sigma_eff * math.sqrt(2.0 * math.pi))
    return norm * np.exp(-0.5 * ((x - mean) / sigma_eff) ** 2)


def lowpass_cascade(signal: np.ndarray, dt_s: float, cutoff_hz: float, poles: int) -> np.ndarray:
    if cutoff_hz <= 0 or poles <= 0:
        return signal.copy()

    tau_s = 1.0 / (2.0 * math.pi * cutoff_hz)
    alpha = math.exp(-dt_s / tau_s)
    filtered = signal.copy()

    for _ in range(poles):
        stage = np.empty_like(filtered)
        stage[0] = filtered[0]
        for index in range(1, filtered.size):
            stage[index] = alpha * stage[index - 1] + (1.0 - alpha) * filtered[index]
        filtered = stage

    return filtered


def crossing_times_ms(v0_m_s: float, z_det_m: float, gravity_m_s2: float) -> tuple[float | None, float | None]:
    discriminant = v0_m_s**2 - 2.0 * gravity_m_s2 * z_det_m
    if discriminant < 0:
        return None, None
    root = math.sqrt(discriminant)
    upward = (v0_m_s - root) / gravity_m_s2
    downward = (v0_m_s + root) / gravity_m_s2
    return upward * 1e3, downward * 1e3


def interpolate_crossing(t0: float, y0: float, t1: float, y1: float, level: float) -> float:
    if y1 == y0:
        return 0.5 * (t0 + t1)
    return t0 + (level - y0) * (t1 - t0) / (y1 - y0)


def estimate_fwhm_ms(time_s: np.ndarray, signal: np.ndarray, peak_index: int) -> float | None:
    peak_value = signal[peak_index]
    if peak_value <= 0:
        return None

    half_max = 0.5 * peak_value
    left = peak_index
    while left > 0 and signal[left] >= half_max:
        left -= 1

    right = peak_index
    while right < signal.size - 1 and signal[right] >= half_max:
        right += 1

    if left == peak_index or right == peak_index:
        return None

    left_time = interpolate_crossing(time_s[left], signal[left], time_s[left + 1], signal[left + 1], half_max)
    right_time = interpolate_crossing(
        time_s[right - 1], signal[right - 1], time_s[right], signal[right], half_max
    )
    return max(0.0, (right_time - left_time) * 1e3)


def compute_peak_metrics(
    label: str,
    time_s: np.ndarray,
    ideal_signal: np.ndarray,
    filtered_signal: np.ndarray,
    mask: np.ndarray,
) -> PeakMetrics | None:
    indices = np.flatnonzero(mask)
    if indices.size < 3:
        return None

    ideal_slice = ideal_signal[indices]
    filtered_slice = filtered_signal[indices]
    if ideal_slice.max() <= 1e-12:
        return None

    ideal_peak_index = indices[int(np.argmax(ideal_slice))]
    filtered_peak_index = indices[int(np.argmax(filtered_slice))]

    ideal_peak = float(ideal_signal[ideal_peak_index])
    filtered_peak = float(filtered_signal[filtered_peak_index])
    ideal_time_ms = float(time_s[ideal_peak_index] * 1e3)
    filtered_time_ms = float(time_s[filtered_peak_index] * 1e3)
    delay_ms = filtered_time_ms - ideal_time_ms

    ideal_fwhm_ms = estimate_fwhm_ms(time_s, ideal_signal, ideal_peak_index)
    filtered_fwhm_ms = estimate_fwhm_ms(time_s, filtered_signal, filtered_peak_index)

    broadening_ms = None
    if ideal_fwhm_ms is not None and filtered_fwhm_ms is not None:
        broadening_ms = filtered_fwhm_ms - ideal_fwhm_ms

    attenuation_pct = None
    if ideal_peak > 0:
        attenuation_pct = 100.0 * (1.0 - filtered_peak / ideal_peak)

    return PeakMetrics(
        label=label,
        ideal_time_ms=ideal_time_ms,
        filtered_time_ms=filtered_time_ms,
        delay_ms=delay_ms,
        ideal_peak=ideal_peak,
        filtered_peak=filtered_peak,
        attenuation_pct=attenuation_pct,
        ideal_fwhm_ms=ideal_fwhm_ms,
        filtered_fwhm_ms=filtered_fwhm_ms,
        broadening_ms=broadening_ms,
    )


def gaussian_curve(time_s: np.ndarray, amplitude: float, center_s: float, sigma_s: float) -> np.ndarray:
    sigma_eff = max(sigma_s, 1e-12)
    return amplitude * np.exp(-0.5 * ((time_s - center_s) / sigma_eff) ** 2)


def gaussian_amplitude_and_sse(
    x_s: np.ndarray,
    y: np.ndarray,
    center_s: float,
    sigma_s: float,
) -> tuple[float, float]:
    basis = gaussian_curve(x_s, 1.0, center_s, sigma_s)
    denominator = float(np.dot(basis, basis))
    if denominator <= 0:
        return 0.0, float(np.dot(y, y))

    amplitude = max(0.0, float(np.dot(y, basis) / denominator))
    residual = amplitude * basis - y
    return amplitude, float(np.dot(residual, residual))


def optimize_gaussian_fit(
    x_s: np.ndarray,
    y: np.ndarray,
    center_guess_s: float,
    sigma_guess_s: float,
) -> tuple[float, float, float, float]:
    if x_s.size < 3:
        raise ValueError('Need at least three samples for Gaussian fitting.')

    dt_s = float(np.median(np.diff(x_s))) if x_s.size > 1 else 1e-6
    best_center_s = center_guess_s
    best_sigma_s = max(sigma_guess_s, 2.0 * dt_s)
    best_amplitude, best_sse = gaussian_amplitude_and_sse(x_s, y, best_center_s, best_sigma_s)

    center_span_s = max(2.0 * dt_s, 0.75 * best_sigma_s)
    log_sigma_span = 0.55

    for _ in range(6):
        center_candidates = np.linspace(best_center_s - center_span_s, best_center_s + center_span_s, 9)
        sigma_candidates = best_sigma_s * np.exp(np.linspace(-log_sigma_span, log_sigma_span, 9))
        for center_s in center_candidates:
            for sigma_s in sigma_candidates:
                amplitude, sse = gaussian_amplitude_and_sse(x_s, y, float(center_s), float(sigma_s))
                if sse < best_sse:
                    best_center_s = float(center_s)
                    best_sigma_s = float(sigma_s)
                    best_amplitude = amplitude
                    best_sse = sse

        center_span_s *= 0.45
        log_sigma_span *= 0.45

    return best_amplitude, best_center_s, best_sigma_s, best_sse


def fit_gaussian_to_peak(
    label: str,
    time_s: np.ndarray,
    signal: np.ndarray,
    mask: np.ndarray,
) -> GaussianFit | None:
    indices = np.flatnonzero(mask)
    if indices.size < 7:
        return None

    x_all = time_s[indices]
    y_all = signal[indices]
    peak = float(y_all.max())
    if peak <= 1e-6:
        return None

    threshold = max(0.03 * peak, 1e-4)
    valid = y_all >= threshold
    if np.count_nonzero(valid) < 7:
        valid = y_all >= max(0.01 * peak, 1e-6)
    if np.count_nonzero(valid) < 7:
        return None

    x_fit = x_all[valid]
    y_fit = y_all[valid]
    dt_s = float(np.median(np.diff(x_fit))) if x_fit.size > 1 else 1e-6

    weights = np.maximum(y_fit, 0.0)
    total_weight = float(weights.sum())
    if total_weight <= 0:
        return None

    center_guess_s = float(np.dot(weights, x_fit) / total_weight)
    variance_s2 = float(np.dot(weights, (x_fit - center_guess_s) ** 2) / total_weight)
    sigma_guess_s = max(math.sqrt(max(variance_s2, 0.0)), 2.0 * dt_s)

    if x_fit.size >= 5:
        coefficients = np.polyfit(x_fit, np.log(np.maximum(y_fit, 1e-12)), 2)
        quadratic, linear, _constant = [float(value) for value in coefficients]
        if quadratic < 0 and np.isfinite(quadratic) and np.isfinite(linear):
            sigma_log_s = math.sqrt(-1.0 / (2.0 * quadratic))
            center_log_s = linear * sigma_log_s**2
            if np.isfinite(center_log_s) and np.isfinite(sigma_log_s) and sigma_log_s > 0:
                center_guess_s = center_log_s
                sigma_guess_s = max(sigma_log_s, 2.0 * dt_s)

    amplitude, center_s, sigma_s, sse = optimize_gaussian_fit(x_fit, y_fit, center_guess_s, sigma_guess_s)
    fit_curve = np.zeros_like(signal)
    fit_curve[indices] = gaussian_curve(x_all, amplitude, center_s, sigma_s)

    fitted_samples = gaussian_curve(x_fit, amplitude, center_s, sigma_s)
    residual = fitted_samples - y_fit
    rmse = math.sqrt(float(np.mean(residual**2)))
    centered = y_fit - float(np.mean(y_fit))
    sst = float(np.dot(centered, centered))
    r_squared = 1.0 - sse / sst if sst > 1e-12 else 1.0

    return GaussianFit(
        label=label,
        amplitude=amplitude,
        center_ms=center_s * 1e3,
        sigma_ms=sigma_s * 1e3,
        fwhm_ms=2.0 * math.sqrt(2.0 * math.log(2.0)) * sigma_s * 1e3,
        rmse=rmse,
        r_squared=r_squared,
        fit_curve=fit_curve,
    )


def format_metric(value: float | None, unit: str, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f} {unit}".strip()


def filter_frequency_response(
    cutoff_hz: float,
    poles: int,
    time_step_s: float,
    enabled: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    nyquist_hz = 0.5 / time_step_s
    if not enabled or cutoff_hz <= 0 or poles <= 0:
        frequency_hz = np.logspace(-1, math.log10(max(10.0, nyquist_hz)), 400)
        return frequency_hz, np.zeros_like(frequency_hz), np.zeros_like(frequency_hz)

    f_min = max(0.1, cutoff_hz / 100.0)
    f_max = min(nyquist_hz, max(10.0 * cutoff_hz, cutoff_hz * 100.0))
    if f_max <= f_min:
        f_max = f_min * 10.0

    frequency_hz = np.logspace(math.log10(f_min), math.log10(f_max), 500)
    response = (1.0 + 1j * frequency_hz / cutoff_hz) ** (-poles)
    magnitude_db = 20.0 * np.log10(np.maximum(np.abs(response), 1e-12))
    phase_deg = np.unwrap(np.angle(response)) * 180.0 / math.pi
    return frequency_hz, magnitude_db, phase_deg


def run_simulation(physics: PhysicsParameters, electronics: ElectronicsParameters) -> SimulationResult:
    if physics.launch_velocity_m_s <= 0:
        raise ValueError("Launch velocity must be positive.")
    if physics.detector_z_m <= 0:
        raise ValueError("Detector height must be positive.")
    if physics.probe_sigma_m <= 0:
        raise ValueError("Probe sigma must be positive.")
    if physics.gravity_m_s2 <= 0:
        raise ValueError("Gravity must be positive.")
    if physics.t_max_s <= 0:
        raise ValueError("Maximum time must be positive.")
    if physics.time_points < 200:
        raise ValueError("Use at least 200 time points.")
    if physics.velocity_points < 301:
        raise ValueError("Use at least 301 velocity points.")
    if electronics.poles < 1:
        raise ValueError("Number of poles must be at least 1.")

    sigma_v = thermal_sigma_v(physics.temperature_uK, physics.atomic_mass_amu)
    sigma_v_eff = max(sigma_v, 1e-6)
    span = 6.0 * sigma_v_eff + 0.08 * physics.launch_velocity_m_s
    v_min = max(0.0, physics.launch_velocity_m_s - span)
    v_max = physics.launch_velocity_m_s + span

    velocity_grid = np.linspace(v_min, v_max, physics.velocity_points)
    velocity_pdf = gaussian_pdf(velocity_grid, physics.launch_velocity_m_s, sigma_v_eff)
    velocity_pdf /= np.trapz(velocity_pdf, velocity_grid)

    full_time = np.linspace(0.0, physics.t_max_s, physics.time_points)
    apex_time_s = physics.launch_velocity_m_s / physics.gravity_m_s2
    if physics.show_return_pass:
        time_s = full_time
    else:
        truncated_end = min(physics.t_max_s, apex_time_s)
        time_s = full_time[full_time <= truncated_end]
        if time_s.size < 200:
            time_s = np.linspace(0.0, truncated_end, 200)

    position_m = time_s[:, None] * velocity_grid[None, :] - 0.5 * physics.gravity_m_s2 * time_s[:, None] ** 2
    probe_weight = np.exp(-0.5 * ((position_m - physics.detector_z_m) / physics.probe_sigma_m) ** 2)
    probe_weight /= math.sqrt(2.0 * math.pi) * physics.probe_sigma_m

    ideal_raw = np.trapz(probe_weight * velocity_pdf[None, :], velocity_grid, axis=1)
    dt_s = time_s[1] - time_s[0]

    if electronics.enable_filter:
        filtered_raw = lowpass_cascade(ideal_raw, dt_s, electronics.cutoff_hz, electronics.poles)
    else:
        filtered_raw = ideal_raw.copy()

    normalization = max(float(ideal_raw.max()), 1e-12)
    ideal_signal = ideal_raw / normalization
    filtered_signal = filtered_raw / normalization

    frequency_hz, magnitude_db, phase_deg = filter_frequency_response(
        electronics.cutoff_hz, electronics.poles, dt_s, electronics.enable_filter
    )

    upward_ms, downward_ms = crossing_times_ms(
        physics.launch_velocity_m_s, physics.detector_z_m, physics.gravity_m_s2
    )

    z_mean_m = physics.launch_velocity_m_s * time_s - 0.5 * physics.gravity_m_s2 * time_s**2
    z_rms_m = sigma_v * time_s
    signal_difference = filtered_signal - ideal_signal

    upward_mask = time_s <= apex_time_s
    downward_mask = time_s > apex_time_s
    upward_metrics = compute_peak_metrics("Upward pass", time_s, ideal_signal, filtered_signal, upward_mask)
    upward_gaussian_fit = fit_gaussian_to_peak("Gaussian fit (upward)", time_s, filtered_signal, upward_mask)
    downward_metrics = None
    downward_gaussian_fit = None
    if physics.show_return_pass and np.any(downward_mask):
        downward_metrics = compute_peak_metrics("Return pass", time_s, ideal_signal, filtered_signal, downward_mask)
        downward_gaussian_fit = fit_gaussian_to_peak(
            "Gaussian fit (return)", time_s, filtered_signal, downward_mask
        )

    return SimulationResult(
        time_s=time_s,
        velocity_grid_m_s=velocity_grid,
        velocity_pdf=velocity_pdf,
        z_mean_m=z_mean_m,
        z_rms_m=z_rms_m,
        ideal_signal=ideal_signal,
        filtered_signal=filtered_signal,
        signal_difference=signal_difference,
        sigma_v_m_s=sigma_v,
        upward_crossing_ms=upward_ms,
        downward_crossing_ms=downward_ms,
        apex_time_ms=apex_time_s * 1e3,
        frequency_hz=frequency_hz,
        magnitude_db=magnitude_db,
        phase_deg=phase_deg,
        upward_metrics=upward_metrics,
        downward_metrics=downward_metrics,
        upward_gaussian_fit=upward_gaussian_fit,
        downward_gaussian_fit=downward_gaussian_fit,
    )


class TofTiaApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("TOF Shape Analyzer: Ballistic Cloud + TIA Low-pass")
        self.root.geometry("1640x980")
        self.root.minsize(1320, 860)

        self.status_var = tk.StringVar(value="Ready.")
        self.current_result: SimulationResult | None = None

        self.species_var = tk.StringVar(value=DEFAULT_SPECIES)
        self.mass_var = tk.StringVar(value=f"{SPECIES_MASS_AMU[DEFAULT_SPECIES]:.9f}")
        self.temperature_var = tk.StringVar(value="5.0")
        self.launch_velocity_var = tk.StringVar(value="4.26")
        self.detector_height_var = tk.StringVar(value="255.0")
        self.probe_sigma_var = tk.StringVar(value="3.0")
        self.gravity_var = tk.StringVar(value="9.81")
        self.show_return_var = tk.BooleanVar(value=True)
        self.t_max_var = tk.StringVar(value="950.0")
        self.time_points_var = tk.StringVar(value="2500")
        self.velocity_points_var = tk.StringVar(value="1601")

        self.enable_filter_var = tk.BooleanVar(value=True)
        self.cutoff_var = tk.StringVar(value="200.0")
        self.poles_var = tk.StringVar(value="1")

        self._build_layout()
        self._populate_model_text()
        self._bind_events()
        self.refresh()

    def _build_layout(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        controls = ttk.Frame(self.root, padding=12)
        controls.grid(row=0, column=0, sticky="nsew")
        controls.columnconfigure(0, weight=1)

        figure_frame = ttk.Frame(self.root, padding=(0, 12, 12, 12))
        figure_frame.grid(row=0, column=1, sticky="nsew")
        figure_frame.columnconfigure(0, weight=1)
        figure_frame.rowconfigure(0, weight=1)

        self._build_controls(controls)
        self._build_figure(figure_frame)

        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            relief="sunken",
            padding=(8, 4),
        )
        status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

    def _build_controls(self, parent: ttk.Frame) -> None:
        source_frame = ttk.LabelFrame(parent, text="Source and Detector", padding=10)
        source_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        source_frame.columnconfigure(1, weight=1)

        self._add_labeled_widget(
            source_frame,
            0,
            "Species",
            ttk.Combobox(
                source_frame,
                textvariable=self.species_var,
                values=list(SPECIES_MASS_AMU.keys()),
                state="readonly",
            ),
        )
        self._add_labeled_entry(source_frame, 1, "Mass (amu)", self.mass_var)
        self._add_labeled_entry(source_frame, 2, "Temperature (uK)", self.temperature_var)
        self._add_labeled_entry(source_frame, 3, "Launch velocity (m/s)", self.launch_velocity_var)
        self._add_labeled_entry(source_frame, 4, "Detector height (mm)", self.detector_height_var)
        self._add_labeled_entry(source_frame, 5, "Probe sigma (mm)", self.probe_sigma_var)
        self._add_labeled_entry(source_frame, 6, "Gravity (m/s^2)", self.gravity_var)

        sampling_frame = ttk.LabelFrame(parent, text="Sampling and Window", padding=10)
        sampling_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        sampling_frame.columnconfigure(1, weight=1)

        self._add_labeled_entry(sampling_frame, 0, "Time span (ms)", self.t_max_var)
        self._add_labeled_entry(sampling_frame, 1, "Time points", self.time_points_var)
        self._add_labeled_entry(sampling_frame, 2, "Velocity points", self.velocity_points_var)
        ttk.Checkbutton(
            sampling_frame,
            text="Include return pass",
            variable=self.show_return_var,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        filter_frame = ttk.LabelFrame(parent, text="TIA Low-pass Model", padding=10)
        filter_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        filter_frame.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            filter_frame,
            text="Enable low-pass filter",
            variable=self.enable_filter_var,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self._add_labeled_entry(filter_frame, 1, "Corner frequency per pole (Hz)", self.cutoff_var)
        self._add_labeled_entry(filter_frame, 2, "Number of poles", self.poles_var)

        action_frame = ttk.Frame(parent, padding=(0, 0, 0, 6))
        action_frame.grid(row=3, column=0, sticky="ew")
        action_frame.columnconfigure((0, 1), weight=1)

        ttk.Button(action_frame, text="Update analysis", command=self.refresh).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(action_frame, text="Reset defaults", command=self.reset_defaults).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )
        ttk.Button(action_frame, text="Export CSV", command=self.export_csv).grid(
            row=1, column=0, sticky="ew", padx=(0, 4), pady=(8, 0)
        )
        ttk.Button(action_frame, text="Save figure", command=self.save_figure).grid(
            row=1, column=1, sticky="ew", padx=(4, 0), pady=(8, 0)
        )

        tabs = ttk.Notebook(parent)
        tabs.grid(row=4, column=0, sticky="nsew", pady=(8, 0))
        parent.rowconfigure(4, weight=1)

        summary_frame = ttk.Frame(tabs, padding=8)
        model_frame = ttk.Frame(tabs, padding=8)
        tabs.add(summary_frame, text="Summary")
        tabs.add(model_frame, text="Model")

        self.summary_text = tk.Text(summary_frame, wrap="word", height=18, width=44)
        self.summary_text.pack(fill="both", expand=True)
        self.summary_text.configure(state="disabled")

        self.model_text = tk.Text(model_frame, wrap="word", height=18, width=44)
        self.model_text.pack(fill="both", expand=True)
        self.model_text.configure(state="disabled")

    def _build_figure(self, parent: ttk.Frame) -> None:
        self.figure = Figure(figsize=(12.5, 8.2), constrained_layout=True)
        grid = self.figure.add_gridspec(2, 2, height_ratios=[1.0, 1.0])

        self.ax_traj = self.figure.add_subplot(grid[0, 0])
        self.ax_signal = self.figure.add_subplot(grid[0, 1])
        self.ax_difference = self.figure.add_subplot(grid[1, 0])
        self.ax_bode = self.figure.add_subplot(grid[1, 1])
        self.ax_bode_phase = self.ax_bode.twinx()

        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        toolbar_frame = ttk.Frame(parent)
        toolbar_frame.grid(row=1, column=0, sticky="ew")
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side="left", fill="x")

    def _add_labeled_widget(self, parent: ttk.Frame, row: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 10))
        widget.grid(row=row, column=1, sticky="ew", pady=4)

    def _add_labeled_entry(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar) -> None:
        entry = ttk.Entry(parent, textvariable=variable)
        self._add_labeled_widget(parent, row, label, entry)

    def _bind_events(self) -> None:
        self.root.bind("<Return>", lambda _event: self.refresh())
        self.species_var.trace_add("write", self._update_mass_from_species)

    def _populate_model_text(self) -> None:
        text = """
Signal model

1. Vertical launch distribution:
   v_z ~ N(v_launch, sigma_v^2),
   sigma_v = sqrt(k_B T / m)

2. Ballistic motion:
   z(t; v_z) = v_z t - 0.5 g t^2

3. Fluorescence collection in the phototube region:
   S_ideal(t) proportional to Integral[P(v_z) * exp(-(z - z_det)^2 / (2 sigma_probe^2)) dv_z]

4. TIA low-pass response:
   H(f) = [1 + i (f / f_c)]^(-N)
   Here N is the number of identical first-order poles.

Interpretation notes

- The app is 1D along the launch axis and ignores transverse expansion.
- The detector is modeled as a Gaussian probe sheet with vertical sigma_probe.
- The filtered trace is computed from the ideal analog signal and then normalized by the ideal peak.
- Peak delay, amplitude attenuation, and FWHM broadening are reported separately for the upward pass and the return pass.
- If the detector is above the ballistic turning point for the mean launch velocity, only the fast tail of the velocity distribution will contribute.
"""
        self.model_text.configure(state="normal")
        self.model_text.delete("1.0", tk.END)
        self.model_text.insert("1.0", text.strip())
        self.model_text.configure(state="disabled")

    def _update_mass_from_species(self, *_args: object) -> None:
        species = self.species_var.get()
        if species != "Custom":
            self.mass_var.set(f"{SPECIES_MASS_AMU[species]:.9f}")

    def reset_defaults(self) -> None:
        self.species_var.set(DEFAULT_SPECIES)
        self.mass_var.set(f"{SPECIES_MASS_AMU[DEFAULT_SPECIES]:.9f}")
        self.temperature_var.set("5.0")
        self.launch_velocity_var.set("4.26")
        self.detector_height_var.set("255.0")
        self.probe_sigma_var.set("3.0")
        self.gravity_var.set("9.81")
        self.show_return_var.set(True)
        self.t_max_var.set("950.0")
        self.time_points_var.set("2500")
        self.velocity_points_var.set("1601")
        self.enable_filter_var.set(True)
        self.cutoff_var.set("200.0")
        self.poles_var.set("1")
        self.refresh()

    def collect_parameters(self) -> tuple[PhysicsParameters, ElectronicsParameters]:
        physics = PhysicsParameters(
            species=self.species_var.get(),
            atomic_mass_amu=float(self.mass_var.get()),
            temperature_uK=float(self.temperature_var.get()),
            launch_velocity_m_s=float(self.launch_velocity_var.get()),
            detector_z_m=float(self.detector_height_var.get()) * 1e-3,
            probe_sigma_m=float(self.probe_sigma_var.get()) * 1e-3,
            gravity_m_s2=float(self.gravity_var.get()),
            show_return_pass=bool(self.show_return_var.get()),
            t_max_s=float(self.t_max_var.get()) * 1e-3,
            time_points=int(self.time_points_var.get()),
            velocity_points=int(self.velocity_points_var.get()),
        )
        electronics = ElectronicsParameters(
            enable_filter=bool(self.enable_filter_var.get()),
            cutoff_hz=float(self.cutoff_var.get()),
            poles=int(self.poles_var.get()),
        )
        return physics, electronics

    def refresh(self) -> None:
        try:
            physics, electronics = self.collect_parameters()
            result = run_simulation(physics, electronics)
        except Exception as error:
            self.status_var.set(f"Error: {error}")
            return

        self.current_result = result
        self._draw_result(physics, electronics, result)
        self._update_summary(physics, electronics, result)
        self.status_var.set(
            f"Updated. sigma_v = {result.sigma_v_m_s * 1e3:.3f} mm/s, "
            f"apex time = {result.apex_time_ms:.2f} ms."
        )

    def _draw_result(
        self,
        physics: PhysicsParameters,
        electronics: ElectronicsParameters,
        result: SimulationResult,
    ) -> None:
        self.ax_traj.clear()
        self.ax_signal.clear()
        self.ax_difference.clear()
        self.ax_bode.clear()
        self.ax_bode_phase.clear()

        time_ms = result.time_s * 1e3
        z_mean_mm = result.z_mean_m * 1e3
        z_low_mm = (result.z_mean_m - result.z_rms_m) * 1e3
        z_high_mm = (result.z_mean_m + result.z_rms_m) * 1e3
        detector_mm = physics.detector_z_m * 1e3
        probe_sigma_mm = physics.probe_sigma_m * 1e3

        self.ax_traj.fill_between(time_ms, z_low_mm, z_high_mm, color="#94d2bd", alpha=0.35, label="1σ cloud spread")
        self.ax_traj.plot(time_ms, z_mean_mm, color="#005f73", linewidth=2.2, label="Mean ballistic trajectory")
        self.ax_traj.axhspan(
            detector_mm - probe_sigma_mm,
            detector_mm + probe_sigma_mm,
            color="#ee9b00",
            alpha=0.18,
            label="Probe sigma band",
        )
        self.ax_traj.axhline(detector_mm, color="#ca6702", linewidth=1.4, linestyle="--", label="Detector center")
        if result.upward_crossing_ms is not None:
            self.ax_traj.axvline(result.upward_crossing_ms, color="#0a9396", linestyle=":", linewidth=1.2)
        if physics.show_return_pass and result.downward_crossing_ms is not None:
            self.ax_traj.axvline(result.downward_crossing_ms, color="#bb3e03", linestyle=":", linewidth=1.2)

        self.ax_traj.set_title("Mean trajectory and cloud spread")
        self.ax_traj.set_xlabel("Time (ms)")
        self.ax_traj.set_ylabel("Height z (mm)")
        self.ax_traj.grid(True, alpha=0.25)
        self.ax_traj.legend(loc="best")

        self.ax_signal.plot(time_ms, result.ideal_signal, color="#005f73", linewidth=2.0, label="Ideal detector signal")
        self.ax_signal.plot(
            time_ms,
            result.filtered_signal,
            color="#bb3e03",
            linewidth=2.0,
            label="After TIA low-pass",
        )
        if result.upward_gaussian_fit is not None:
            self.ax_signal.plot(
                time_ms,
                result.upward_gaussian_fit.fit_curve,
                color="#001219",
                linewidth=1.8,
                linestyle="--",
                label="Gaussian fit (upward)",
            )
        if result.downward_gaussian_fit is not None:
            self.ax_signal.plot(
                time_ms,
                result.downward_gaussian_fit.fit_curve,
                color="#6c757d",
                linewidth=1.8,
                linestyle="--",
                label="Gaussian fit (return)",
            )
        self.ax_signal.set_title("TOF signal at the phototube")
        self.ax_signal.set_xlabel("Time (ms)")
        self.ax_signal.set_ylabel("Normalized signal")
        self.ax_signal.grid(True, alpha=0.25)
        self.ax_signal.legend(loc="best")

        self.ax_difference.axhline(0.0, color="0.35", linewidth=1.0, linestyle="--")
        self.ax_difference.fill_between(
            time_ms,
            0.0,
            result.signal_difference,
            where=result.signal_difference >= 0.0,
            color="#0a9396",
            alpha=0.35,
        )
        self.ax_difference.fill_between(
            time_ms,
            0.0,
            result.signal_difference,
            where=result.signal_difference < 0.0,
            color="#ae2012",
            alpha=0.35,
        )
        self.ax_difference.plot(time_ms, result.signal_difference, color="#9b2226", linewidth=1.8)
        self.ax_difference.set_title("Waveform distortion from the low-pass stage")
        self.ax_difference.set_xlabel("Time (ms)")
        self.ax_difference.set_ylabel("Filtered - ideal")
        self.ax_difference.grid(True, alpha=0.25)

        self.ax_bode.semilogx(
            result.frequency_hz,
            result.magnitude_db,
            color="#005f73",
            linewidth=2.0,
            label="Magnitude",
        )
        self.ax_bode_phase.semilogx(
            result.frequency_hz,
            result.phase_deg,
            color="#bb3e03",
            linewidth=1.8,
            label="Phase",
        )
        if electronics.enable_filter and electronics.cutoff_hz > 0:
            self.ax_bode.axvline(
                electronics.cutoff_hz,
                color="0.4",
                linestyle=":",
                linewidth=1.2,
                label="Corner frequency",
            )

        self.ax_bode.set_title("Electronics transfer function")
        self.ax_bode.set_xlabel("Frequency (Hz)")
        self.ax_bode.set_ylabel("Magnitude (dB)", color="#005f73")
        self.ax_bode_phase.set_ylabel("Phase (deg)", color="#bb3e03")
        self.ax_bode.grid(True, which="both", alpha=0.25)

        self.canvas.draw_idle()

    def _update_summary(
        self,
        physics: PhysicsParameters,
        electronics: ElectronicsParameters,
        result: SimulationResult,
    ) -> None:
        upward = result.upward_metrics
        downward = result.downward_metrics
        upward_fit = result.upward_gaussian_fit
        downward_fit = result.downward_gaussian_fit
        sample_rate_hz = 1.0 / (result.time_s[1] - result.time_s[0])

        lines = [
            "Core parameters",
            f"- Species: {physics.species} ({physics.atomic_mass_amu:.6f} amu)",
            f"- Temperature: {physics.temperature_uK:.3f} uK",
            f"- Launch velocity: {physics.launch_velocity_m_s:.4f} m/s",
            f"- Detector height: {physics.detector_z_m * 1e3:.3f} mm",
            f"- Probe sigma: {physics.probe_sigma_m * 1e3:.3f} mm",
            f"- Gravity: {physics.gravity_m_s2:.5f} m/s^2",
            "",
            "Derived quantities",
            f"- 1D thermal sigma_v: {result.sigma_v_m_s * 1e3:.3f} mm/s",
            f"- Mean apex time: {result.apex_time_ms:.3f} ms",
            f"- Mean upward crossing: {format_metric(result.upward_crossing_ms, 'ms')}",
            f"- Mean return crossing: {format_metric(result.downward_crossing_ms, 'ms') if physics.show_return_pass else 'not shown'}",
            f"- Effective sampling rate: {sample_rate_hz:.1f} Hz",
            "",
            "Electronics",
            f"- Low-pass enabled: {'yes' if electronics.enable_filter else 'no'}",
            f"- Corner frequency per pole: {electronics.cutoff_hz:.3f} Hz",
            f"- Number of poles: {electronics.poles:d}",
            "",
        ]

        if upward_fit is not None:
            lines.extend(
                [
                    "Gaussian fit to filtered upward peak",
                    f"- Center: {format_metric(upward_fit.center_ms, 'ms')}",
                    f"- Sigma: {format_metric(upward_fit.sigma_ms, 'ms')}",
                    f"- FWHM: {format_metric(upward_fit.fwhm_ms, 'ms')}",
                    f"- RMSE: {format_metric(upward_fit.rmse, '')}",
                    f"- R^2: {format_metric(upward_fit.r_squared, '')}",
                    "",
                ]
            )

        if physics.show_return_pass and downward_fit is not None:
            lines.extend(
                [
                    "Gaussian fit to filtered return peak",
                    f"- Center: {format_metric(downward_fit.center_ms, 'ms')}",
                    f"- Sigma: {format_metric(downward_fit.sigma_ms, 'ms')}",
                    f"- FWHM: {format_metric(downward_fit.fwhm_ms, 'ms')}",
                    f"- RMSE: {format_metric(downward_fit.rmse, '')}",
                    f"- R^2: {format_metric(downward_fit.r_squared, '')}",
                    "",
                ]
            )

        if upward is not None:
            lines.extend(
                [
                    "Upward pass metrics",
                    f"- Ideal peak time: {format_metric(upward.ideal_time_ms, 'ms')}",
                    f"- Filtered peak time: {format_metric(upward.filtered_time_ms, 'ms')}",
                    f"- Peak delay: {format_metric(upward.delay_ms, 'ms')}",
                    f"- Peak attenuation: {format_metric(upward.attenuation_pct, '%')}",
                    f"- Ideal FWHM: {format_metric(upward.ideal_fwhm_ms, 'ms')}",
                    f"- Filtered FWHM: {format_metric(upward.filtered_fwhm_ms, 'ms')}",
                    f"- FWHM broadening: {format_metric(upward.broadening_ms, 'ms')}",
                    "",
                ]
            )

        if physics.show_return_pass and downward is not None:
            lines.extend(
                [
                    "Return pass metrics",
                    f"- Ideal peak time: {format_metric(downward.ideal_time_ms, 'ms')}",
                    f"- Filtered peak time: {format_metric(downward.filtered_time_ms, 'ms')}",
                    f"- Peak delay: {format_metric(downward.delay_ms, 'ms')}",
                    f"- Peak attenuation: {format_metric(downward.attenuation_pct, '%')}",
                    f"- Ideal FWHM: {format_metric(downward.ideal_fwhm_ms, 'ms')}",
                    f"- Filtered FWHM: {format_metric(downward.filtered_fwhm_ms, 'ms')}",
                    f"- FWHM broadening: {format_metric(downward.broadening_ms, 'ms')}",
                ]
            )

        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", tk.END)
        self.summary_text.insert("1.0", "\n".join(lines))
        self.summary_text.configure(state="disabled")

    def export_csv(self) -> None:
        if self.current_result is None:
            messagebox.showerror("No data", "Run the analysis first.")
            return

        output_path = filedialog.asksaveasfilename(
            title="Export TOF traces",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="tof_tia_trace.csv",
        )
        if not output_path:
            return

        data = np.column_stack(
            [
                self.current_result.time_s * 1e3,
                self.current_result.z_mean_m * 1e3,
                self.current_result.z_rms_m * 1e3,
                self.current_result.ideal_signal,
                self.current_result.filtered_signal,
                self.current_result.signal_difference,
            ]
        )
        header = (
            "time_ms,z_mean_mm,z_rms_mm,ideal_signal_norm,filtered_signal_norm,"
            "filtered_minus_ideal"
        )
        np.savetxt(output_path, data, delimiter=",", header=header, comments="")
        self.status_var.set(f"CSV exported to {output_path}")

    def save_figure(self) -> None:
        output_path = filedialog.asksaveasfilename(
            title="Save figure",
            defaultextension=".png",
            filetypes=[
                ("PNG image", "*.png"),
                ("PDF file", "*.pdf"),
                ("SVG file", "*.svg"),
                ("All files", "*.*"),
            ],
            initialfile="tof_tia_analysis.png",
        )
        if not output_path:
            return

        self.figure.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
        self.status_var.set(f"Figure saved to {output_path}")


def main() -> None:
    root = tk.Tk()
    ttk.Style(root).theme_use("clam")
    app = TofTiaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
