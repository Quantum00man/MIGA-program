#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from tkinter import filedialog, messagebox, ttk

from simulator_core import (
    FringeParameters,
    PhaseScanResult,
    PhaseScanSettings,
    SavedConfiguration,
    ScanSettings,
    SimulationResult,
    build_phase_scan_summary_lines,
    build_summary_lines,
    default_configuration,
    default_phase_scan_settings,
    load_configuration_json,
    save_configuration_json,
    save_csv,
    save_phase_scan_csv,
    simulate_dual_ai,
    simulate_phase_scan_lissajous,
)


@dataclass(frozen=True)
class ParameterSpec:
    key: str
    label: str
    unit: str
    help_text: str


DEFAULT_HELP = (
    "Each fringe can use the built-in cosine model or a custom formula.\n"
    "Formula variables: t2_ms2 (x-axis, ms^2), t_ms, phase_scan_rad, "
    "period_t2_ms2, phase_rad, offset, peak_to_peak.\n"
    "Allowed functions include sin, cos, tan, exp, log, sqrt, clip, where, minimum, maximum.\n\n"
    "The left plot always scans T and displays the fringes against T^2 in ms^2. "
    "The right plot can either reuse that T scan or hold T fixed and scan phase to build a second Lissajous curve."
)

MODEL_TYPE_CHOICES = {
    "cosine": "Cosine parameters",
    "formula": "Custom formula",
}
LISSAJOUS_MODE_CHOICES = {
    "t_scan": "Use T scan",
    "phase_scan": "Fix T and scan phase",
}


def t2_ms2_to_t_ms(values):
    array = np.asarray(values, dtype=float)
    return np.sqrt(np.clip(array, 0.0, None))


def t_ms_to_t2_ms2(values):
    array = np.asarray(values, dtype=float)
    return np.square(np.clip(array, 0.0, None))


FORMULA_HELP_TEXT = (
    "Custom formula evaluated for each fringe. Available symbols: t2_ms2, t_ms, phase_scan_rad, "
    "period_t2_ms2, phase_rad, offset, peak_to_peak, pi, e. Example: "
    "offset + 0.5*peak_to_peak*cos(2*pi*t2_ms2/period_t2_ms2 + phase_rad + phase_scan_rad)"
)

PARAMETER_SPECS = {
    "t_min_ms": ParameterSpec(
        key="t_min_ms",
        label="T min",
        unit="ms",
        help_text="Scan start in milliseconds. The model converts T to T^2 internally.",
    ),
    "t_max_ms": ParameterSpec(
        key="t_max_ms",
        label="T max",
        unit="ms",
        help_text="Scan stop in milliseconds. Keep T >= 0 for a physical pulse-separation scan.",
    ),
    "n_points": ParameterSpec(
        key="n_points",
        label="Points",
        unit="",
        help_text="Number of simulated scan samples. More points give a smoother fringe.",
    ),
    "clip_to_probability": ParameterSpec(
        key="clip_to_probability",
        label="Clip to [0, 1]",
        unit="",
        help_text=(
            "Clamp the simulated output probability to the physical range [0, 1]. "
            "Disable it if you want to inspect the raw signal."
        ),
    ),
    "upper_model_type": ParameterSpec(
        key="upper_model_type",
        label="Definition",
        unit="",
        help_text="Choose between the built-in cosine model and a custom formula for the upper interferometer.",
    ),
    "upper_period": ParameterSpec(
        key="upper_period",
        label="Period in T^2",
        unit="ms^2",
        help_text=(
            "Fringe period in T^2 units. A value of 20 ms^2 means one full 2*pi phase advance "
            "when T^2 increases by 20 ms^2."
        ),
    ),
    "upper_phase": ParameterSpec(
        key="upper_phase",
        label="Phase parameter",
        unit="rad",
        help_text=(
            "Static phase parameter for the upper interferometer. In formula mode this is exposed as phase_rad."
        ),
    ),
    "upper_offset": ParameterSpec(
        key="upper_offset",
        label="Center offset",
        unit="P",
        help_text="Fringe center. In formula mode this is exposed as offset.",
    ),
    "upper_pp": ParameterSpec(
        key="upper_pp",
        label="Peak-to-peak",
        unit="P",
        help_text="Peak-to-peak amplitude. In formula mode this is exposed as peak_to_peak.",
    ),
    "upper_formula": ParameterSpec(
        key="upper_formula",
        label="Formula",
        unit="",
        help_text=FORMULA_HELP_TEXT,
    ),
    "lower_model_type": ParameterSpec(
        key="lower_model_type",
        label="Definition",
        unit="",
        help_text="Choose between the built-in cosine model and a custom formula for the lower interferometer.",
    ),
    "lower_period": ParameterSpec(
        key="lower_period",
        label="Period in T^2",
        unit="ms^2",
        help_text=(
            "Fringe period in T^2 units for the lower interferometer. This parameter is also available "
            "inside a custom formula as period_t2_ms2."
        ),
    ),
    "lower_phase": ParameterSpec(
        key="lower_phase",
        label="Phase parameter",
        unit="rad",
        help_text=(
            "Static phase parameter for the lower interferometer. In formula mode this is exposed as phase_rad."
        ),
    ),
    "lower_offset": ParameterSpec(
        key="lower_offset",
        label="Center offset",
        unit="P",
        help_text="Fringe center for the lower interferometer. In formula mode this is exposed as offset.",
    ),
    "lower_pp": ParameterSpec(
        key="lower_pp",
        label="Peak-to-peak",
        unit="P",
        help_text=(
            "Peak-to-peak amplitude for the lower interferometer. In formula mode this is exposed as peak_to_peak."
        ),
    ),
    "lower_formula": ParameterSpec(
        key="lower_formula",
        label="Formula",
        unit="",
        help_text=FORMULA_HELP_TEXT,
    ),
    "lissajous_mode": ParameterSpec(
        key="lissajous_mode",
        label="Lissajous source",
        unit="",
        help_text=(
            "Choose whether the right-hand Lissajous curve comes from the T scan or from a phase sweep at fixed T."
        ),
    ),
    "phase_scan_fixed_t_ms": ParameterSpec(
        key="phase_scan_fixed_t_ms",
        label="Fixed T",
        unit="ms",
        help_text=(
            "Pulse separation held constant while scanning phase. The resulting Lissajous is evaluated at this T and uses T^2 = T*T internally."
        ),
    ),
    "phase_scan_min": ParameterSpec(
        key="phase_scan_min",
        label="Phase min",
        unit="rad",
        help_text="Start value of the scanned phase variable phase_scan_rad.",
    ),
    "phase_scan_max": ParameterSpec(
        key="phase_scan_max",
        label="Phase max",
        unit="rad",
        help_text="Stop value of the scanned phase variable phase_scan_rad.",
    ),
    "phase_scan_points": ParameterSpec(
        key="phase_scan_points",
        label="Phase points",
        unit="",
        help_text="Number of samples used to trace the fixed-T phase-scan Lissajous curve.",
    ),
}


class DualInterferometerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Dual Atom Interferometer Fringe and Lissajous Simulator")
        self.geometry("1540x980")
        self.minsize(1320, 860)

        self.output_dir = Path(__file__).resolve().parent / "outputs"
        self.output_dir.mkdir(exist_ok=True)

        self.current_result: SimulationResult | None = None
        self.current_phase_result: PhaseScanResult | None = None
        self.current_lissajous_mode = "t_scan"
        self.vars: dict[str, tk.Variable] = {}
        self.help_var = tk.StringVar(value=DEFAULT_HELP)
        self.summary_var = tk.StringVar(value="Run the simulation to populate the live summary.")
        self.status_var = tk.StringVar(value="Ready.")

        self._configure_style()
        self._build_ui()
        self._load_defaults()
        self.update_plots()
        self.bind("<Return>", lambda _event: self.update_plots())

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background="#f3f5f7")
        style.configure("TLabelframe", background="#f3f5f7")
        style.configure("TLabelframe.Label", background="#f3f5f7", font=("Arial", 11, "bold"))
        style.configure("TLabel", background="#f3f5f7", font=("Arial", 10))
        style.configure("Header.TLabel", font=("Arial", 12, "bold"))
        style.configure("Small.TLabel", font=("Arial", 9))
        style.configure("TButton", padding=(10, 6), font=("Arial", 10))
        style.configure("Primary.TButton", padding=(10, 6), font=("Arial", 10, "bold"))
        style.configure("TEntry", padding=4)
        style.configure("TCheckbutton", background="#f3f5f7")

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        controls_shell = ttk.Frame(root)
        controls_shell.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        controls_shell.columnconfigure(0, weight=1)
        controls_shell.rowconfigure(0, weight=1)

        self.controls_canvas = tk.Canvas(
            controls_shell,
            background="#f3f5f7",
            highlightthickness=0,
            borderwidth=0,
            width=500,
        )
        controls_scrollbar = ttk.Scrollbar(
            controls_shell,
            orient="vertical",
            command=self.controls_canvas.yview,
        )
        self.controls_canvas.configure(yscrollcommand=controls_scrollbar.set)
        self.controls_canvas.grid(row=0, column=0, sticky="nsew")
        controls_scrollbar.grid(row=0, column=1, sticky="ns")

        controls = ttk.Frame(self.controls_canvas)
        self.controls_window = self.controls_canvas.create_window((0, 0), window=controls, anchor="nw")
        controls.bind("<Configure>", self._update_controls_scrollregion)
        self.controls_canvas.bind("<Configure>", self._resize_controls_canvas_window)
        self._bind_controls_mousewheel(controls)

        plots = ttk.Frame(root)
        plots.grid(row=0, column=1, sticky="nsew")
        plots.rowconfigure(0, weight=1)
        plots.columnconfigure(0, weight=1)

        title = ttk.Label(
            controls,
            text="Gradient-Mode Controls",
            style="Header.TLabel",
        )
        title.grid(row=0, column=0, sticky="w", pady=(0, 8))

        scan_frame = ttk.LabelFrame(controls, text="Scan Settings", padding=10)
        scan_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self._build_scan_frame(scan_frame)

        upper_frame = ttk.LabelFrame(controls, text="MIGA21", padding=10)
        upper_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self._build_upper_frame(upper_frame)

        lower_frame = ttk.LabelFrame(controls, text="MIGA22", padding=10)
        lower_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self._build_lower_frame(lower_frame)

        lissajous_frame = ttk.LabelFrame(controls, text="Lissajous Settings", padding=10)
        lissajous_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        self._build_lissajous_frame(lissajous_frame)

        action_frame = ttk.LabelFrame(controls, text="Actions", padding=10)
        action_frame.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        self._build_actions(action_frame)

        help_frame = ttk.LabelFrame(controls, text="Parameter Help", padding=10)
        help_frame.grid(row=6, column=0, sticky="ew", pady=(0, 10))
        help_label = ttk.Label(
            help_frame,
            textvariable=self.help_var,
            justify="left",
            wraplength=440,
        )
        help_label.grid(row=0, column=0, sticky="w")

        summary_frame = ttk.LabelFrame(controls, text="Live Summary", padding=10)
        summary_frame.grid(row=7, column=0, sticky="ew")
        summary_label = ttk.Label(
            summary_frame,
            textvariable=self.summary_var,
            justify="left",
            wraplength=440,
        )
        summary_label.grid(row=0, column=0, sticky="w")

        self.figure = Figure(figsize=(12.1, 7.0), dpi=120, constrained_layout=True)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plots)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        toolbar = NavigationToolbar2Tk(self.canvas, plots, pack_toolbar=False)
        toolbar.update()
        toolbar.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        status = ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(12, 6))
        status.grid(row=1, column=0, sticky="ew")

    def _update_controls_scrollregion(self, _event: tk.Event | None = None) -> None:
        self.controls_canvas.configure(scrollregion=self.controls_canvas.bbox("all"))

    def _resize_controls_canvas_window(self, event: tk.Event) -> None:
        self.controls_canvas.itemconfigure(self.controls_window, width=event.width)

    def _bind_controls_mousewheel(self, controls: ttk.Frame) -> None:
        for widget in (self.controls_canvas, controls):
            widget.bind("<Enter>", self._enable_controls_mousewheel)
            widget.bind("<Leave>", self._disable_controls_mousewheel)

    def _enable_controls_mousewheel(self, _event: tk.Event) -> None:
        self.bind_all("<MouseWheel>", self._on_controls_mousewheel)
        self.bind_all("<Button-4>", self._on_controls_mousewheel)
        self.bind_all("<Button-5>", self._on_controls_mousewheel)

    def _disable_controls_mousewheel(self, _event: tk.Event) -> None:
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")

    def _on_controls_mousewheel(self, event: tk.Event) -> None:
        if getattr(event, "num", None) == 4:
            self.controls_canvas.yview_scroll(-1, "units")
            return
        if getattr(event, "num", None) == 5:
            self.controls_canvas.yview_scroll(1, "units")
            return

        delta = getattr(event, "delta", 0)
        if delta:
            self.controls_canvas.yview_scroll(int(-delta / 120), "units")

    def _build_scan_frame(self, frame: ttk.LabelFrame) -> None:
        desc = ttk.Label(
            frame,
            text="Enter the scan range in T (ms). The fringe plot stays on a T^2 axis in ms^2.",
            wraplength=430,
            justify="left",
            style="Small.TLabel",
        )
        desc.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        self._add_entry(frame, "t_min_ms", row=1, column=0)
        self._add_entry(frame, "t_max_ms", row=2, column=0)
        self._add_entry(frame, "n_points", row=3, column=0)

        clip_var = tk.BooleanVar(value=False)
        self.vars["clip_to_probability"] = clip_var
        checkbox = ttk.Checkbutton(
            frame,
            text="Clip output probability to [0, 1]",
            variable=clip_var,
            command=lambda: self._show_help("clip_to_probability"),
        )
        checkbox.grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self._bind_help_widgets(checkbox, "clip_to_probability")

    def _build_upper_frame(self, frame: ttk.LabelFrame) -> None:
        desc = ttk.Label(
            frame,
            text=(
                "The upper fringe can use cosine parameters directly or evaluate a custom formula. "
                "In formula mode the x variable is t2_ms2 in ms^2."
            ),
            wraplength=430,
            justify="left",
            style="Small.TLabel",
        )
        desc.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self._add_combobox(frame, "upper_model_type", row=1, column=0, values=list(MODEL_TYPE_CHOICES.values()))
        self._add_entry(frame, "upper_period", row=2, column=0)
        self._add_entry(frame, "upper_phase", row=3, column=0)
        self._add_entry(frame, "upper_offset", row=4, column=0)
        self._add_entry(frame, "upper_pp", row=5, column=0)
        self._add_formula_entry(frame, "upper_formula", row=6, column=0)

    def _build_lower_frame(self, frame: ttk.LabelFrame) -> None:
        desc = ttk.Label(
            frame,
            text=(
                "The lower fringe supports the same two definition modes. Use phase_scan_rad inside the formula "
                "if you want the fixed-T phase sweep to drive the Lissajous figure."
            ),
            wraplength=430,
            justify="left",
            style="Small.TLabel",
        )
        desc.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self._add_combobox(frame, "lower_model_type", row=1, column=0, values=list(MODEL_TYPE_CHOICES.values()))
        self._add_entry(frame, "lower_period", row=2, column=0)
        self._add_entry(frame, "lower_phase", row=3, column=0)
        self._add_entry(frame, "lower_offset", row=4, column=0)
        self._add_entry(frame, "lower_pp", row=5, column=0)
        self._add_formula_entry(frame, "lower_formula", row=6, column=0)

    def _build_lissajous_frame(self, frame: ttk.LabelFrame) -> None:
        desc = ttk.Label(
            frame,
            text=(
                "The right subplot can either trace the Lissajous curve along the T scan or hold T fixed "
                "and scan the shared phase variable phase_scan_rad."
            ),
            wraplength=430,
            justify="left",
            style="Small.TLabel",
        )
        desc.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self._add_combobox(frame, "lissajous_mode", row=1, column=0, values=list(LISSAJOUS_MODE_CHOICES.values()))
        self._add_entry(frame, "phase_scan_fixed_t_ms", row=2, column=0)
        self._add_entry(frame, "phase_scan_min", row=3, column=0)
        self._add_entry(frame, "phase_scan_max", row=4, column=0)
        self._add_entry(frame, "phase_scan_points", row=5, column=0)

    def _build_actions(self, frame: ttk.LabelFrame) -> None:
        update_button = ttk.Button(frame, text="Update Plots", style="Primary.TButton", command=self.update_plots)
        update_button.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        reset_button = ttk.Button(frame, text="Reset Defaults", command=self.reset_defaults)
        reset_button.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        load_button = ttk.Button(frame, text="Load JSON", command=self.load_configuration_bundle)
        load_button.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        figure_button = ttk.Button(frame, text="Save Figure", command=self.save_figure)
        figure_button.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        csv_button = ttk.Button(frame, text="Save CSV + JSON", command=self.save_data_bundle)
        csv_button.grid(row=4, column=0, sticky="ew")

    def _add_entry(self, frame: ttk.LabelFrame, key: str, *, row: int, column: int) -> None:
        spec = PARAMETER_SPECS[key]
        label = ttk.Label(frame, text=spec.label)
        label.grid(row=row, column=column, sticky="w", pady=4)

        var = tk.StringVar()
        self.vars[key] = var

        entry = ttk.Entry(frame, textvariable=var, width=16)
        entry.grid(row=row, column=column + 1, sticky="ew", padx=(10, 8), pady=4)
        unit_text = spec.unit if spec.unit else " "
        unit = ttk.Label(frame, text=unit_text, style="Small.TLabel")
        unit.grid(row=row, column=column + 2, sticky="w", pady=4)

        frame.columnconfigure(column + 1, weight=1)
        self._bind_help_widgets(label, key)
        self._bind_help_widgets(entry, key)
        self._bind_help_widgets(unit, key)

    def _add_combobox(
        self,
        frame: ttk.LabelFrame,
        key: str,
        *,
        row: int,
        column: int,
        values: list[str],
    ) -> None:
        spec = PARAMETER_SPECS[key]
        label = ttk.Label(frame, text=spec.label)
        label.grid(row=row, column=column, sticky="w", pady=4)

        var = tk.StringVar()
        self.vars[key] = var

        combo = ttk.Combobox(frame, textvariable=var, values=values, state="readonly", width=26)
        combo.grid(row=row, column=column + 1, sticky="ew", padx=(10, 8), pady=4)
        unit = ttk.Label(frame, text=" ", style="Small.TLabel")
        unit.grid(row=row, column=column + 2, sticky="w", pady=4)

        combo.bind("<<ComboboxSelected>>", lambda _event, name=key: self._show_help(name))
        frame.columnconfigure(column + 1, weight=1)
        self._bind_help_widgets(label, key)
        self._bind_help_widgets(combo, key)
        self._bind_help_widgets(unit, key)

    def _add_formula_entry(self, frame: ttk.LabelFrame, key: str, *, row: int, column: int) -> None:
        spec = PARAMETER_SPECS[key]
        label = ttk.Label(frame, text=spec.label)
        label.grid(row=row, column=column, sticky="nw", pady=(6, 4))

        var = tk.StringVar()
        self.vars[key] = var

        entry = ttk.Entry(frame, textvariable=var, width=48)
        entry.grid(row=row, column=column + 1, columnspan=2, sticky="ew", padx=(10, 0), pady=(6, 4))

        frame.columnconfigure(column + 1, weight=1)
        self._bind_help_widgets(label, key)
        self._bind_help_widgets(entry, key)

    def _bind_help_widgets(self, widget: tk.Widget, key: str) -> None:
        widget.bind("<Enter>", lambda _event, name=key: self._show_help(name))
        widget.bind("<FocusIn>", lambda _event, name=key: self._show_help(name))

    def _show_help(self, key: str) -> None:
        self.help_var.set(PARAMETER_SPECS[key].help_text)

    def _load_defaults(self) -> None:
        scan, upper, lower = default_configuration()
        phase_scan = default_phase_scan_settings()
        defaults = {
            "t_min_ms": f"{scan.t_min_ms:.3f}",
            "t_max_ms": f"{scan.t_max_ms:.3f}",
            "n_points": str(scan.n_points),
            "upper_model_type": MODEL_TYPE_CHOICES[upper.model_type],
            "upper_period": f"{upper.period_t2_ms2:.3f}",
            "upper_phase": f"{upper.phase_rad:.3f}",
            "upper_offset": f"{upper.offset:.3f}",
            "upper_pp": f"{upper.peak_to_peak:.3f}",
            "upper_formula": upper.formula,
            "lower_model_type": MODEL_TYPE_CHOICES[lower.model_type],
            "lower_period": f"{lower.period_t2_ms2:.3f}",
            "lower_phase": f"{lower.phase_rad:.3f}",
            "lower_offset": f"{lower.offset:.3f}",
            "lower_pp": f"{lower.peak_to_peak:.3f}",
            "lower_formula": lower.formula,
            "lissajous_mode": LISSAJOUS_MODE_CHOICES["t_scan"],
            "phase_scan_fixed_t_ms": f"{phase_scan.fixed_t_ms:.3f}",
            "phase_scan_min": f"{phase_scan.phase_min_rad:.3f}",
            "phase_scan_max": f"{phase_scan.phase_max_rad:.3f}",
            "phase_scan_points": str(phase_scan.n_points),
        }
        for key, value in defaults.items():
            variable = self.vars.get(key)
            if isinstance(variable, tk.StringVar):
                variable.set(value)
        clip_var = self.vars["clip_to_probability"]
        if isinstance(clip_var, tk.BooleanVar):
            clip_var.set(scan.clip_to_probability)
        self.help_var.set(DEFAULT_HELP)

    @staticmethod
    def _format_loaded_float(value: float) -> str:
        return f"{float(value):.3f}"

    @staticmethod
    def _format_loaded_int(value: int) -> str:
        return str(int(value))

    def _apply_loaded_configuration(self, config: SavedConfiguration) -> None:
        phase_scan = config.phase_scan or default_phase_scan_settings()
        values = {
            "t_min_ms": self._format_loaded_float(config.scan.t_min_ms),
            "t_max_ms": self._format_loaded_float(config.scan.t_max_ms),
            "n_points": self._format_loaded_int(config.scan.n_points),
            "upper_model_type": MODEL_TYPE_CHOICES[config.upper.model_type],
            "upper_period": self._format_loaded_float(config.upper.period_t2_ms2),
            "upper_phase": self._format_loaded_float(config.upper.phase_rad),
            "upper_offset": self._format_loaded_float(config.upper.offset),
            "upper_pp": self._format_loaded_float(config.upper.peak_to_peak),
            "upper_formula": config.upper.formula,
            "lower_model_type": MODEL_TYPE_CHOICES[config.lower.model_type],
            "lower_period": self._format_loaded_float(config.lower.period_t2_ms2),
            "lower_phase": self._format_loaded_float(config.lower.phase_rad),
            "lower_offset": self._format_loaded_float(config.lower.offset),
            "lower_pp": self._format_loaded_float(config.lower.peak_to_peak),
            "lower_formula": config.lower.formula,
            "lissajous_mode": LISSAJOUS_MODE_CHOICES[config.lissajous_mode],
            "phase_scan_fixed_t_ms": self._format_loaded_float(phase_scan.fixed_t_ms),
            "phase_scan_min": self._format_loaded_float(phase_scan.phase_min_rad),
            "phase_scan_max": self._format_loaded_float(phase_scan.phase_max_rad),
            "phase_scan_points": self._format_loaded_int(phase_scan.n_points),
        }
        for key, value in values.items():
            variable = self.vars.get(key)
            if isinstance(variable, tk.StringVar):
                variable.set(value)

        clip_var = self.vars["clip_to_probability"]
        if isinstance(clip_var, tk.BooleanVar):
            clip_var.set(config.scan.clip_to_probability)

        self.help_var.set(DEFAULT_HELP)
        self.controls_canvas.yview_moveto(0.0)

    def collect_inputs(
        self,
    ) -> tuple[ScanSettings, FringeParameters, FringeParameters, PhaseScanSettings | None, str]:
        def get_float(key: str) -> float:
            variable = self.vars[key]
            if not isinstance(variable, tk.StringVar):
                raise ValueError(f"Unexpected variable type for {key}.")
            return float(variable.get())

        def get_int(key: str) -> int:
            variable = self.vars[key]
            if not isinstance(variable, tk.StringVar):
                raise ValueError(f"Unexpected variable type for {key}.")
            return int(float(variable.get()))

        def get_str(key: str) -> str:
            variable = self.vars[key]
            if not isinstance(variable, tk.StringVar):
                raise ValueError(f"Unexpected variable type for {key}.")
            return variable.get().strip()

        clip_var = self.vars["clip_to_probability"]
        if not isinstance(clip_var, tk.BooleanVar):
            raise ValueError("Unexpected variable type for clip_to_probability.")

        scan = ScanSettings(
            t_min_ms=get_float("t_min_ms"),
            t_max_ms=get_float("t_max_ms"),
            n_points=get_int("n_points"),
            clip_to_probability=clip_var.get(),
        )

        upper_mode_label = get_str("upper_model_type")
        lower_mode_label = get_str("lower_model_type")
        upper_model_type = self._resolve_choice_key(upper_mode_label, MODEL_TYPE_CHOICES, "upper model")
        lower_model_type = self._resolve_choice_key(lower_mode_label, MODEL_TYPE_CHOICES, "lower model")

        upper = FringeParameters(
            label="MIGA21",
            period_t2_ms2=get_float("upper_period"),
            phase_rad=get_float("upper_phase"),
            offset=get_float("upper_offset"),
            peak_to_peak=get_float("upper_pp"),
            color="#0f6c5c",
            model_type=upper_model_type,
            formula=get_str("upper_formula"),
        )
        lower = FringeParameters(
            label="MIGA22",
            period_t2_ms2=get_float("lower_period"),
            phase_rad=get_float("lower_phase"),
            offset=get_float("lower_offset"),
            peak_to_peak=get_float("lower_pp"),
            color="#c45b12",
            model_type=lower_model_type,
            formula=get_str("lower_formula"),
        )

        lissajous_mode_label = get_str("lissajous_mode")
        lissajous_mode = self._resolve_choice_key(
            lissajous_mode_label,
            LISSAJOUS_MODE_CHOICES,
            "Lissajous source",
        )

        phase_scan: PhaseScanSettings | None = None
        if lissajous_mode == "phase_scan":
            phase_scan = PhaseScanSettings(
                fixed_t_ms=get_float("phase_scan_fixed_t_ms"),
                phase_min_rad=get_float("phase_scan_min"),
                phase_max_rad=get_float("phase_scan_max"),
                n_points=get_int("phase_scan_points"),
            )

        return scan, upper, lower, phase_scan, lissajous_mode

    def _resolve_choice_key(self, label: str, choices: dict[str, str], field_name: str) -> str:
        for key, value in choices.items():
            if value == label:
                return key
        raise ValueError(f"Invalid selection for {field_name}: {label!r}.")

    def update_plots(self) -> bool:
        try:
            scan, upper, lower, phase_scan, lissajous_mode = self.collect_inputs()
            result = simulate_dual_ai(scan, upper, lower)
            phase_result = None
            if lissajous_mode == "phase_scan":
                if phase_scan is None:
                    raise ValueError("Phase-scan settings are missing.")
                phase_result = simulate_phase_scan_lissajous(
                    phase_scan,
                    upper,
                    lower,
                    clip_to_probability=scan.clip_to_probability,
                )
        except ValueError as exc:
            self.status_var.set("Update failed.")
            messagebox.showerror("Invalid input", str(exc), parent=self)
            return False

        self.current_result = result
        self.current_phase_result = phase_result
        self.current_lissajous_mode = lissajous_mode
        self._draw_result(result, phase_result=phase_result, lissajous_mode=lissajous_mode)

        summary_lines = build_summary_lines(result)
        if phase_result is not None:
            summary_lines.extend(["", *build_phase_scan_summary_lines(phase_result)])
        self.summary_var.set("\n".join(summary_lines))

        if lissajous_mode == "phase_scan":
            self.status_var.set("Simulation updated. Right panel uses fixed-T phase scan.")
        else:
            self.status_var.set("Simulation updated. Right panel uses the T scan trajectory.")

        return True

    def _draw_result(
        self,
        result: SimulationResult,
        *,
        phase_result: PhaseScanResult | None,
        lissajous_mode: str,
    ) -> None:
        self.figure.clear()
        grid = self.figure.add_gridspec(1, 2, width_ratios=[1.65, 1.0])

        ax_fringe = self.figure.add_subplot(grid[0, 0])
        ax_lissajous = self.figure.add_subplot(grid[0, 1])

        ax_fringe.plot(
            result.t2_ms2,
            result.upper_probability,
            color=result.upper.color,
            linewidth=2.1,
            label=result.upper.label,
        )
        ax_fringe.plot(
            result.t2_ms2,
            result.lower_probability,
            color=result.lower.color,
            linewidth=2.1,
            label=result.lower.label,
        )
        ax_fringe.set_title("Dual Interferometer Fringes", fontsize=12, fontweight="bold")
        ax_fringe.set_xlabel("T^2 (ms^2)")
        ax_fringe.set_ylabel("Output probability P")
        ax_fringe.grid(True, alpha=0.28, linewidth=0.8)
        ax_fringe.legend(frameon=False, loc="upper right")
        ax_fringe.set_xlim(float(result.t2_ms2[0]), float(result.t2_ms2[-1]))

        top_axis = ax_fringe.secondary_xaxis("top", functions=(t2_ms2_to_t_ms, t_ms_to_t2_ms2))
        top_axis.set_xlabel("T (ms)")

        combined_probability = np.concatenate([result.upper_probability, result.lower_probability])
        self._set_probability_limits(ax_fringe, combined_probability, result.scan.clip_to_probability)

        ax_fringe.text(
            0.02,
            0.03,
            self._build_fringe_caption(result),
            transform=ax_fringe.transAxes,
            fontsize=9,
            bbox={"facecolor": "white", "edgecolor": "#ccd3d9", "boxstyle": "round,pad=0.25", "alpha": 0.95},
        )

        if lissajous_mode == "phase_scan" and phase_result is not None:
            x_values = phase_result.upper_probability
            y_values = phase_result.lower_probability
            curve_color = "#3d405b"
            title = "Lissajous Plot (fixed T, phase scan)"
            detail_text = (
                f"T = {phase_result.settings.fixed_t_ms:.3f} ms\n"
                f"T^2 = {phase_result.fixed_t2_ms2:.3f} ms^2\n"
                f"phase = {phase_result.phase_rad[0]:.3f} to {phase_result.phase_rad[-1]:.3f} rad"
            )
        else:
            x_values = result.upper_probability
            y_values = result.lower_probability
            curve_color = "#284b63"
            title = "Lissajous Plot (T scan)"
            detail_text = (
                f"T = {result.t_ms[0]:.3f} to {result.t_ms[-1]:.3f} ms\n"
                f"T^2 = {result.t2_ms2[0]:.3f} to {result.t2_ms2[-1]:.3f} ms^2"
            )

        ax_lissajous.plot(
            x_values,
            y_values,
            color=curve_color,
            linewidth=2.0,
        )
        ax_lissajous.scatter(
            x_values[0],
            y_values[0],
            s=48,
            color="#222222",
            label="Start",
            zorder=3,
        )
        ax_lissajous.scatter(
            x_values[-1],
            y_values[-1],
            s=52,
            marker="s",
            color="#c1121f",
            label="End",
            zorder=3,
        )
        ax_lissajous.set_title(title, fontsize=12, fontweight="bold")
        ax_lissajous.set_xlabel(f"{result.upper.label} probability")
        ax_lissajous.set_ylabel(f"{result.lower.label} probability")
        ax_lissajous.grid(True, alpha=0.28, linewidth=0.8)
        ax_lissajous.legend(frameon=False, loc="upper right")
        ax_lissajous.set_aspect("equal", adjustable="box")
        lissajous_probability = np.concatenate([x_values, y_values])
        self._set_probability_limits(
            ax_lissajous,
            lissajous_probability,
            result.scan.clip_to_probability,
            both_axes=True,
        )
        ax_lissajous.text(
            0.03,
            0.03,
            detail_text,
            transform=ax_lissajous.transAxes,
            fontsize=9,
            bbox={"facecolor": "white", "edgecolor": "#ccd3d9", "boxstyle": "round,pad=0.25", "alpha": 0.95},
        )

        self.canvas.draw_idle()

    def _build_fringe_caption(self, result: SimulationResult) -> str:
        model_types = {result.upper.model_type, result.lower.model_type}
        if model_types == {"cosine"}:
            return "P(T^2) = offset + 0.5*pp*cos(2*pi*T^2/period + phase)"
        if model_types == {"formula"}:
            return "Formula mode: use t2_ms2 and phase_scan_rad in ms^2 / rad"
        return "Mixed mode: cosine + custom formula on the same T^2 axis"

    def _set_probability_limits(
        self,
        axis,
        probability_values: np.ndarray,
        clip_to_probability: bool,
        *,
        both_axes: bool = False,
    ) -> None:
        if clip_to_probability:
            low, high = -0.02, 1.02
        else:
            min_value = float(np.min(probability_values))
            max_value = float(np.max(probability_values))
            spread = max(max_value - min_value, 0.08)
            margin = 0.08 * spread
            low = min(-0.02, min_value - margin)
            high = max(1.02, max_value + margin)

        axis.set_ylim(low, high)
        if both_axes:
            axis.set_xlim(low, high)

    def reset_defaults(self) -> None:
        self._load_defaults()
        self.update_plots()
        self.status_var.set("Default parameters restored.")

    def load_configuration_bundle(self) -> None:
        default_path = self.output_dir / "dual_ai_lissajous.json"
        file_path = filedialog.askopenfilename(
            parent=self,
            title="Load simulation configuration",
            initialdir=self.output_dir,
            initialfile=default_path.name,
            filetypes=[("JSON configuration", "*.json"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            config = load_configuration_json(file_path)
            self._apply_loaded_configuration(config)
        except (OSError, ValueError) as exc:
            self.status_var.set("Load failed.")
            messagebox.showerror("Load failed", str(exc), parent=self)
            return

        if not self.update_plots():
            return

        self.status_var.set(f"Loaded {Path(file_path).name} and recomputed.")

    def save_figure(self) -> None:
        if self.current_result is None:
            messagebox.showerror("No data", "Run the simulation before saving a figure.", parent=self)
            return

        default_path = self.output_dir / "dual_ai_lissajous.png"
        file_path = filedialog.asksaveasfilename(
            parent=self,
            title="Save figure",
            initialdir=self.output_dir,
            initialfile=default_path.name,
            defaultextension=".png",
            filetypes=[("PNG figure", "*.png"), ("PDF figure", "*.pdf"), ("All files", "*.*")],
        )
        if not file_path:
            return

        self.figure.savefig(file_path, dpi=300, bbox_inches="tight")
        self.status_var.set(f"Figure saved to {file_path}")

    def save_data_bundle(self) -> None:
        if self.current_result is None:
            messagebox.showerror("No data", "Run the simulation before saving data.", parent=self)
            return

        default_path = self.output_dir / "dual_ai_lissajous.csv"
        file_path = filedialog.asksaveasfilename(
            parent=self,
            title="Save simulation data",
            initialdir=self.output_dir,
            initialfile=default_path.name,
            defaultextension=".csv",
            filetypes=[("CSV table", "*.csv"), ("All files", "*.*")],
        )
        if not file_path:
            return

        csv_path = Path(file_path)
        json_path = csv_path.with_suffix(".json")
        save_csv(self.current_result, csv_path)
        saved_names = [csv_path.name, json_path.name]

        if self.current_phase_result is not None:
            phase_csv_path = csv_path.with_name(f"{csv_path.stem}_phase_scan.csv")
            save_phase_scan_csv(self.current_phase_result, phase_csv_path)
            saved_names.insert(1, phase_csv_path.name)

        save_configuration_json(
            self.current_result,
            json_path,
            phase_scan_result=self.current_phase_result,
            lissajous_mode=self.current_lissajous_mode,
        )
        self.status_var.set(f"Saved {' + '.join(saved_names)}")


def main() -> None:
    app = DualInterferometerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
