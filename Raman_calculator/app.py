from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import MaxNLocator

from raman_model import (
    DEFAULT_ATTENUATION,
    DEFAULT_DESACC_MHZ,
    DEFAULT_EXPANSION_TIME_MS,
    DEFAULT_GAIN,
    DEFAULT_INITIAL_CLOUD_SIGMA_MM,
    DEFAULT_P1_MW,
    DEFAULT_P2_MW,
    DEFAULT_RADIAL_CUTOFF_WAISTS,
    DEFAULT_RADIAL_POINTS,
    DEFAULT_TAU_MAX_US,
    DEFAULT_TAU_MIN_US,
    DEFAULT_TAU_POINTS,
    DEFAULT_TEMPERATURE_UK,
    DEFAULT_TWO_PHOTON_DETUNING_KHZ,
    DEFAULT_VELOCITY_CUTOFF_SIGMA,
    DEFAULT_VELOCITY_POINTS,
    DEFAULT_W0_MM,
    RamanSimulationParameters,
    RamanSimulationResult,
    choose_display_time_axis,
    simulate_rabi_oscillation,
)
from raman_detuning_model import (
    DEFAULT_ALPHA_DEG,
    DEFAULT_LASER_WAVELENGTH_M,
    DEFAULT_RECOIL_FREQUENCY_KHZ,
    DEFAULT_VZ_M_S,
    FALLING_DOWN,
    FLYING_UP,
    TRANSITION_F1_TO_F2,
    TRANSITION_F2_TO_F1,
    CalibrationResult,
    DetuningConstants,
    LightShiftCorrectionResult,
    VelocityInversionResult,
    calibrate_alpha_and_vx_from_scans,
    compute_detuning_khz,
    compute_light_shift_correction,
    compute_vx_from_detuning_auto,
)


APP_BACKGROUND = "#eef2f7"
CARD_BACKGROUND = "#ffffff"
INK = "#18324a"
MUTED = "#5f7387"
ACCENT = "#0c5a89"
ACCENT_SOFT = "#dce9f4"
CURVE_A = "#0b5c8a"
CURVE_B = "#af5a2a"
MARKER_A = "#0a4263"
MARKER_B = "#8d451b"
PLOT_TITLE_FONT = "DejaVu Serif"
LOCKED_RESULT_COLORS = [
    "#af5a2a",
    "#2d7d6b",
    "#8e5ea2",
    "#b5475a",
    "#5f6caf",
    "#8c6d1f",
]
TIME_UNIT_FACTORS = {"s": 1.0, "ms": 1e3, "us": 1e6, "ns": 1e9}
TRANSITION_CHOICES = [TRANSITION_F1_TO_F2, TRANSITION_F2_TO_F1]
MOTION_CHOICES = [FLYING_UP, FALLING_DOWN]

PRESET_FILE = Path(__file__).with_name("presets.json")
BOOLEAN_FIELDS = {"use_separate_longitudinal_temperature"}
INTEGER_FIELDS = {"tau_points", "radial_points", "velocity_points"}

DEFAULT_FIELD_VALUES: dict[str, object] = {
    "transverse_temperature_uK": DEFAULT_TEMPERATURE_UK,
    "use_separate_longitudinal_temperature": False,
    "longitudinal_temperature_uK": DEFAULT_TEMPERATURE_UK,
    "desacc_mhz": DEFAULT_DESACC_MHZ,
    "p1_mw": DEFAULT_P1_MW,
    "p2_mw": DEFAULT_P2_MW,
    "w0_mm": DEFAULT_W0_MM,
    "tau_min_us": DEFAULT_TAU_MIN_US,
    "tau_max_us": DEFAULT_TAU_MAX_US,
    "tau_points": DEFAULT_TAU_POINTS,
    "expansion_time_ms": DEFAULT_EXPANSION_TIME_MS,
    "initial_cloud_sigma_mm": DEFAULT_INITIAL_CLOUD_SIGMA_MM,
    "two_photon_detuning_khz": DEFAULT_TWO_PHOTON_DETUNING_KHZ,
    "attenuation": DEFAULT_ATTENUATION,
    "gain": DEFAULT_GAIN,
    "radial_points": DEFAULT_RADIAL_POINTS,
    "velocity_points": DEFAULT_VELOCITY_POINTS,
    "radial_cutoff_waists": DEFAULT_RADIAL_CUTOFF_WAISTS,
    "velocity_cutoff_sigma": DEFAULT_VELOCITY_CUTOFF_SIGMA,
}

BUNDLED_PRESETS: dict[str, dict[str, object]] = {
    "Original Raman.txt Defaults": {},
    "Raman Down": {
        "p1_mw": 14.0,
        "p2_mw": 7.0,
        "w0_mm": 11.5,
        "expansion_time_ms": 56.0,
        "desacc_mhz": -1300.0,
    },
    "Raman Up": {
        "p1_mw": 150.0,
        "p2_mw": 70.0,
        "w0_mm": 30.0,
        "expansion_time_ms": 78.0,
    },
    "Raman Labeling": {
        "p1_mw": 150.0,
        "p2_mw": 70.0,
        "w0_mm": 30.0,
        "expansion_time_ms": 780.0,
    },
}

BUNDLED_PRESET_NOTES: dict[str, str] = {
    "Original Raman.txt Defaults": (
        "Reference starting point translated directly from Raman.txt."
    ),
    "Raman Down": (
        "Preset for Raman down selection: P1 = 14 mW, P2 = 7 mW, w0 = 11.5 mm, "
        "T = 56 ms, desacc / 2pi = -1300 MHz."
    ),
    "Raman Up": (
        "Preset for Raman up selection: P1 = 150 mW, P2 = 70 mW, w0 = 30 mm, "
        "T = 78 ms, all other values inherited from the default set."
    ),
    "Raman Labeling": (
        "Preset for Raman labeling: P1 = 150 mW, P2 = 70 mW, w0 = 30 mm, "
        "T = 780 ms, all other values inherited from the default set."
    ),
}


@dataclass(slots=True)
class SimulationSnapshot:
    params: RamanSimulationParameters
    result: RamanSimulationResult


@dataclass(slots=True)
class DisplaySimulation:
    identifier: str
    params: RamanSimulationParameters
    result: RamanSimulationResult
    color: str
    is_current: bool
    legend_label: str
    cloud_time_plot: np.ndarray


class ScrollableFrame(ttk.Frame):
    def __init__(self, master: tk.Misc, **kwargs: object) -> None:
        super().__init__(master, **kwargs)

        canvas = tk.Canvas(
            self,
            borderwidth=0,
            highlightthickness=0,
            background=APP_BACKGROUND,
        )
        # Use a deliberately visible scrollbar instead of the platform ttk default.
        # Some desktop themes render the ttk thumb so narrowly that it is effectively
        # invisible, especially on a compact display.
        scrollbar = tk.Scrollbar(
            self,
            orient="vertical",
            command=canvas.yview,
            width=16,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            background=ACCENT,
            activebackground="#0a4c73",
            troughcolor=ACCENT_SOFT,
        )
        self.inner = ttk.Frame(canvas, style="App.TFrame")

        self.inner.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        window_id = canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window_id, width=event.width),
        )

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y", padx=(8, 0))

        self._canvas = canvas
        self._scrollbar = scrollbar
        self._bind_mousewheel(canvas)

    def _bind_mousewheel(self, canvas: tk.Canvas) -> None:
        def on_mousewheel(event: tk.Event[tk.Misc]) -> None:
            if not self._contains_pointer(event):
                return
            delta = int(-event.delta / 120) if event.delta else 0
            if delta:
                canvas.yview_scroll(delta, "units")

        def on_linux_mousewheel(event: tk.Event[tk.Misc]) -> None:
            if not self._contains_pointer(event):
                return
            canvas.yview_scroll(-1 if event.num == 4 else 1, "units")

        # Bind globally so scrolling also works while the pointer is over an Entry,
        # Label, or Combobox inside the canvas. The pointer check ensures that only
        # the scrollable panel currently under the mouse handles the event.
        canvas.bind_all("<MouseWheel>", on_mousewheel, add="+")
        canvas.bind_all("<Button-4>", on_linux_mousewheel, add="+")
        canvas.bind_all("<Button-5>", on_linux_mousewheel, add="+")

    def _contains_pointer(self, event: tk.Event[tk.Misc]) -> bool:
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self:
                return True
            widget = widget.master
        return False


class RamanCalculatorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Raman Transition Calculator")
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = max(640, min(1440, screen_width - 40))
        window_height = max(480, min(920, screen_height - 80))
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.minsize(min(960, window_width), min(640, window_height))
        self.root.configure(background=APP_BACKGROUND)

        self._configure_style()

        self.variables: dict[str, tk.Variable] = {}
        self.field_entries: dict[str, ttk.Entry] = {}
        self.last_result: RamanSimulationResult | None = None
        self.last_params: RamanSimulationParameters | None = None
        self.is_running = False
        self.locked_results: list[SimulationSnapshot] = []
        self.display_runs_cache: list[DisplaySimulation] = []
        self.cloud_time_unit_for_plot = "ms"
        self.user_presets = self._load_user_presets()
        self.preset_name_var = tk.StringVar(value="Original Raman.txt Defaults")
        self.preset_info_var = tk.StringVar(
            value="Bundled preset translated directly from Raman.txt."
        )
        self.auto_scale_rabi_var = tk.BooleanVar(value=True)
        self.plot_hover_var = tk.StringVar(
            value="Move the cursor over a curve to inspect the nearest sample."
        )
        self.plot_marker_var = tk.StringVar(
            value="Click inside a plot to pin a marker. Double-click to reset the view."
        )
        self.overlay_status_var = tk.StringVar(
            value="Displaying the current simulation result only."
        )
        self.plot_default_limits: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
        self.crosshair_lines: dict[str, tuple[object, object]] = {}
        self.marker_artists: dict[str, dict[str, object]] = {}
        self.toolbar: NavigationToolbar2Tk | None = None
        self.detuning_vars = self._create_detuning_variables()
        self.last_detuning_calibration: CalibrationResult | None = None

        self.status_var = tk.StringVar(
            value="Ready. Review the input definitions, then run the simulation."
        )

        self._build_layout()
        self._refresh_header_action_state()
        self._configure_temperature_linkage()
        self.reset_to_defaults()
        self.root.after(250, self.run_simulation)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        default_font = ("Segoe UI", 10)
        self.root.option_add("*Font", default_font)
        self.root.option_add("*TCombobox*Listbox.font", default_font)

        style.configure("App.TFrame", background=APP_BACKGROUND)
        style.configure(
            "Card.TFrame",
            background=CARD_BACKGROUND,
            relief="flat",
        )
        style.configure(
            "Title.TLabel",
            background=APP_BACKGROUND,
            foreground=INK,
            font=("Segoe UI Semibold", 20),
        )
        style.configure(
            "Subtitle.TLabel",
            background=APP_BACKGROUND,
            foreground=MUTED,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Section.TLabelframe",
            background=CARD_BACKGROUND,
            bordercolor=ACCENT_SOFT,
            relief="solid",
            borderwidth=1,
            padding=16,
        )
        style.configure(
            "Section.TLabelframe.Label",
            background=CARD_BACKGROUND,
            foreground=INK,
            font=("Segoe UI Semibold", 11),
        )
        style.configure(
            "Compact.TLabelframe",
            background=CARD_BACKGROUND,
            bordercolor=ACCENT_SOFT,
            relief="solid",
            borderwidth=1,
            padding=9,
        )
        style.configure(
            "Compact.TLabelframe.Label",
            background=CARD_BACKGROUND,
            foreground=INK,
            font=("Segoe UI Semibold", 10),
        )
        style.configure("Card.TLabel", background=CARD_BACKGROUND, foreground=INK)
        style.configure(
            "Field.TLabel",
            background=CARD_BACKGROUND,
            foreground=INK,
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "Muted.TLabel",
            background=CARD_BACKGROUND,
            foreground=MUTED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Status.TLabel",
            background=APP_BACKGROUND,
            foreground=MUTED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "ResultTitle.TLabel",
            background=CARD_BACKGROUND,
            foreground=INK,
            font=("Segoe UI Semibold", 17),
        )
        style.configure(
            "ResultSymbol.TLabel",
            background="#f4f8fb",
            foreground=ACCENT,
            font=("Segoe UI Semibold", 12),
        )
        style.configure(
            "ResultValue.TLabel",
            background="#f4f8fb",
            foreground=INK,
            font=("Segoe UI Semibold", 13),
        )
        style.configure(
            "ResultCaption.TLabel",
            background="#f4f8fb",
            foreground=MUTED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Equation.TLabel",
            background=CARD_BACKGROUND,
            foreground=INK,
            font=("Segoe UI", 12),
        )
        style.configure("Metric.TFrame", background="#f4f8fb", relief="solid", borderwidth=1)
        style.configure(
            "Primary.TButton",
            background=ACCENT,
            foreground="white",
            borderwidth=0,
            focuscolor=ACCENT,
            padding=(14, 8),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "Primary.TButton",
            background=[("active", "#0a4c73"), ("pressed", "#093d5d")],
            foreground=[("disabled", "#d6e1ea")],
        )
        style.configure(
            "Secondary.TButton",
            background=CARD_BACKGROUND,
            foreground=INK,
            bordercolor=ACCENT_SOFT,
            padding=(12, 8),
        )
        style.map("Secondary.TButton", background=[("active", "#f3f7fb")])
        style.configure(
            "Notebook.TNotebook",
            background=APP_BACKGROUND,
            borderwidth=0,
        )
        style.configure(
            "Notebook.TNotebook.Tab",
            padding=(16, 8),
            background="#dfe7ef",
            foreground=INK,
        )
        style.map(
            "Notebook.TNotebook.Tab",
            background=[("selected", CARD_BACKGROUND)],
            foreground=[("selected", ACCENT)],
        )

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, style="App.TFrame", padding=(22, 18, 22, 18))
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer, style="App.TFrame")
        header.pack(fill="x", pady=(0, 16))
        header.columnconfigure(0, weight=1)

        title_block = ttk.Frame(header, style="App.TFrame")
        title_block.grid(row=0, column=0, sticky="w")
        ttk.Label(
            title_block,
            text="Raman Transition Calculator",
            style="Title.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            title_block,
            text=(
                "Python translation of Raman.txt with an experimental interface for "
                "Rabi-oscillation prediction and atom-cloud expansion tracking."
            ),
            style="Subtitle.TLabel",
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(3, 0))

        self._build_header_actions(header)

        self.main_notebook = ttk.Notebook(outer, style="Notebook.TNotebook")
        self.main_notebook.pack(fill="both", expand=True)
        self.simulation_page = ttk.Frame(self.main_notebook, style="App.TFrame", padding=4)
        self.detuning_page = ttk.Frame(self.main_notebook, style="App.TFrame", padding=4)
        self.main_notebook.add(self.simulation_page, text="Simulation")
        self.main_notebook.add(self.detuning_page, text="Detuning")
        self.main_notebook.bind("<<NotebookTabChanged>>", self._on_main_page_changed)

        self._build_simulation_page(self.simulation_page)
        self._build_detuning_page(self.detuning_page)

        status_bar = ttk.Frame(outer, style="App.TFrame")
        status_bar.pack(fill="x", pady=(12, 0))
        ttk.Label(status_bar, textvariable=self.status_var, style="Status.TLabel").pack(
            anchor="w"
        )

    def _build_simulation_page(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=0)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        controls_card = ttk.Frame(parent, style="Card.TFrame", padding=18)
        controls_card.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        controls_card.configure(width=420)
        controls_card.grid_propagate(False)
        controls_card.rowconfigure(0, weight=1)
        controls_card.columnconfigure(0, weight=1)

        scrollable = ScrollableFrame(controls_card, style="App.TFrame")
        scrollable.grid(row=0, column=0, sticky="nsew")
        self.controls_parent = scrollable.inner

        self._build_control_sections()

        right_panel = ttk.Frame(parent, style="App.TFrame")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.rowconfigure(0, weight=1)
        right_panel.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(right_panel, style="Notebook.TNotebook")
        notebook.grid(row=0, column=0, sticky="nsew")

        plots_tab = ttk.Frame(notebook, style="Card.TFrame", padding=14)
        derived_tab = ttk.Frame(notebook, style="Card.TFrame", padding=18)
        notes_tab = ttk.Frame(notebook, style="Card.TFrame", padding=18)
        notebook.add(plots_tab, text="Plots")
        notebook.add(derived_tab, text="Derived Values")
        notebook.add(notes_tab, text="Model Notes")

        self._build_plot_tab(plots_tab)
        self._build_derived_tab(derived_tab)
        self._build_notes_tab(notes_tab)

    def _build_header_actions(self, parent: ttk.Frame) -> None:
        action_block = ttk.Frame(parent, style="App.TFrame")
        action_block.grid(row=0, column=1, sticky="ne")

        self.run_button = ttk.Button(
            action_block,
            text="Run Simulation",
            style="Primary.TButton",
            command=self.run_simulation,
        )
        self.run_button.grid(row=0, column=0, padx=(0, 8), pady=(0, 8), sticky="ew")

        self.lock_button = ttk.Button(
            action_block,
            text="Lock Current",
            style="Secondary.TButton",
            command=self.lock_current_result,
        )
        self.lock_button.grid(row=0, column=1, padx=(0, 8), pady=(0, 8), sticky="ew")

        self.export_button = ttk.Button(
            action_block,
            text="Export Current CSV",
            style="Secondary.TButton",
            command=self.export_last_result,
        )
        self.export_button.grid(row=0, column=2, pady=(0, 8), sticky="ew")

        self.reset_button = ttk.Button(
            action_block,
            text="Reset to Defaults",
            style="Secondary.TButton",
            command=self.reset_to_defaults,
        )
        self.reset_button.grid(row=1, column=0, padx=(0, 8), sticky="ew")

        self.clear_locked_button = ttk.Button(
            action_block,
            text="Clear Locked",
            style="Secondary.TButton",
            command=self.clear_locked_results,
        )
        self.clear_locked_button.grid(row=1, column=1, padx=(0, 8), sticky="ew")

        ttk.Label(
            action_block,
            text="Use locked results to keep reference curves while scanning new parameters.",
            style="Status.TLabel",
            wraplength=420,
            justify="right",
        ).grid(row=1, column=2, sticky="e")

    def _create_detuning_variables(self) -> dict[str, tk.Variable]:
        return {
            "mode": tk.StringVar(value="vx2detuning"),
            "input_label": tk.StringVar(value="vx (mm/s):"),
            "input_value": tk.StringVar(),
            "motion": tk.StringVar(value=FLYING_UP),
            "transition": tk.StringVar(value=TRANSITION_F1_TO_F2),
            "vz_m_s": tk.StringVar(value=f"{DEFAULT_VZ_M_S:.5f}"),
            "alpha_deg": tk.StringVar(value=f"{DEFAULT_ALPHA_DEG:.4f}"),
            "laser_wavelength_nm": tk.StringVar(
                value=f"{DEFAULT_LASER_WAVELENGTH_M * 1e9:.3f}"
            ),
            "recoil_frequency_khz": tk.StringVar(
                value=f"{DEFAULT_RECOIL_FREQUENCY_KHZ:.3f}"
            ),
            "calibration_up_khz": tk.StringVar(),
            "calibration_down_khz": tk.StringVar(),
            "calibration_transition": tk.StringVar(value=TRANSITION_F1_TO_F2),
            "light_shift_delta_plus_khz": tk.StringVar(),
            "light_shift_delta_minus_khz": tk.StringVar(),
            "light_shift_transition": tk.StringVar(value=TRANSITION_F1_TO_F2),
            "calculator_result": tk.StringVar(
                value="Choose a mode, enter the value, and run the detuning calculator."
            ),
            "calibration_result": tk.StringVar(
                value=(
                    "Enter the signed flying-up and falling-down resonance detunings to "
                    "recover alpha and vx."
                )
            ),
            "light_shift_result": tk.StringVar(
                value=(
                    "Enter the measured counter-propagating delta+ and delta- peak "
                    "centers to extract and remove their common light shift."
                )
            ),
        }

    def _simulation_tab_active(self) -> bool:
        return self.main_notebook.nametowidget(self.main_notebook.select()) is self.simulation_page

    def _on_main_page_changed(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        self._refresh_header_action_state()

    def _refresh_header_action_state(self) -> None:
        simulation_active = self._simulation_tab_active()
        shared_state = "normal" if simulation_active and not self.is_running else "disabled"
        self.run_button.configure(state=shared_state)
        self.lock_button.configure(state=shared_state)
        self.reset_button.configure(state=shared_state)
        self.export_button.configure(state=shared_state)
        self.clear_locked_button.configure(state=shared_state)

    def _build_detuning_page(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=0)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        controls_card = ttk.Frame(parent, style="Card.TFrame", padding=18)
        controls_card.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        controls_card.configure(width=380)
        controls_card.grid_propagate(False)
        controls_card.rowconfigure(0, weight=1)
        controls_card.columnconfigure(0, weight=1)

        scrollable = ScrollableFrame(controls_card, style="App.TFrame")
        scrollable.grid(row=0, column=0, sticky="nsew")
        controls = scrollable.inner

        self._build_detuning_constants_section(controls)
        self._build_detuning_calculator_section(controls)
        self._build_light_shift_correction_section(controls)
        self._build_detuning_calibration_section(controls)

        results_panel = ttk.Frame(parent, style="App.TFrame")
        results_panel.grid(row=0, column=1, sticky="nsew")
        results_panel.rowconfigure(0, weight=1)
        results_panel.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(results_panel, style="Notebook.TNotebook")
        notebook.grid(row=0, column=0, sticky="nsew")

        calculator_tab = ttk.Frame(notebook, style="Card.TFrame", padding=18)
        light_shift_tab = ttk.Frame(notebook, style="Card.TFrame", padding=18)
        calibration_tab = ttk.Frame(notebook, style="Card.TFrame", padding=18)
        notes_tab = ttk.Frame(notebook, style="Card.TFrame", padding=18)
        notebook.add(calculator_tab, text="Calculator")
        notebook.add(light_shift_tab, text="Light Shift")
        notebook.add(calibration_tab, text="Calibration")
        notebook.add(notes_tab, text="Notes")

        self._build_calculator_result_panel(calculator_tab)
        self._build_light_shift_result_panel(light_shift_tab)
        self._build_calibration_result_panel(calibration_tab)
        self.detuning_results_notebook = notebook
        self.detuning_calculator_tab = calculator_tab
        self.detuning_light_shift_tab = light_shift_tab
        self.detuning_calibration_tab = calibration_tab

        notes = tk.Text(
            notes_tab,
            wrap="word",
            background=CARD_BACKGROUND,
            foreground=INK,
            relief="flat",
            font=("Segoe UI", 10),
            padx=8,
            pady=8,
        )
        notes.pack(fill="both", expand=True)
        notes.insert(
            "1.0",
            (
                "Detuning model scope\n\n"
                "This page integrates the original Raman_deturning_4.0.py logic without "
                "changing the sign conventions or inversion rules.\n\n"
                "Forward calculation\n\n"
                "Given vx, the tool reports the four physical detuning branches:\n"
                "flying up, Delta>0\n"
                "flying up, Delta<0\n"
                "falling down, Delta>0\n"
                "falling down, Delta<0\n\n"
                "Inverse calculation\n\n"
                "Given a signed detuning value and the selected motion direction, the tool "
                "automatically chooses the correct branch and returns vx.\n\n"
                "Calibration\n\n"
                "Provide the signed resonance detuning extracted from a flying-up scan and a "
                "falling-down scan for the same transition direction. The tool then reconstructs "
                "alpha and vx using the same detuning model. The calibrated alpha can be applied "
                "back to the detuning constants for subsequent calculations.\n"
                "\nLight-shift correction\n\n"
                "For a measured counter-propagating delta+ / delta- peak pair, the tool "
                "uses their mean to extract the common differential light shift after "
                "subtracting the signed recoil center. Zeeman and frequency-reference "
                "offsets are intentionally neglected.\n"
            ),
        )
        notes.configure(state="disabled")

    def _make_metric_card(
        self,
        parent: ttk.Frame,
        symbol: str,
        caption: str,
        variable: tk.StringVar,
        row: int,
        column: int,
        columnspan: int = 1,
    ) -> ttk.Frame:
        card = ttk.Frame(parent, style="Metric.TFrame", padding=(14, 10))
        card.grid(
            row=row,
            column=column,
            columnspan=columnspan,
            sticky="nsew",
            padx=5,
            pady=5,
        )
        card.columnconfigure(1, weight=1)
        ttk.Label(card, text=symbol, style="ResultSymbol.TLabel").grid(
            row=0, column=0, rowspan=2, sticky="w", padx=(0, 14)
        )
        ttk.Label(card, textvariable=variable, style="ResultValue.TLabel").grid(
            row=0, column=1, sticky="e"
        )
        ttk.Label(card, text=caption, style="ResultCaption.TLabel").grid(
            row=1, column=1, sticky="e"
        )
        return card

    def _result_header(
        self, parent: ttk.Frame, title: str, subtitle: str
    ) -> None:
        ttk.Label(parent, text=title, style="ResultTitle.TLabel").pack(anchor="w")
        ttk.Label(
            parent,
            text=subtitle,
            style="Muted.TLabel",
            wraplength=480,
            justify="left",
        ).pack(anchor="w", pady=(4, 14))

    def _make_result_row(
        self,
        parent: ttk.LabelFrame,
        row: int,
        symbol: str,
        caption: str,
        variable: tk.StringVar,
    ) -> None:
        ttk.Label(parent, text=symbol, style="Field.TLabel", width=6).grid(
            row=row, column=0, sticky="w", pady=3
        )
        ttk.Label(parent, text=caption, style="Muted.TLabel").grid(
            row=row, column=1, sticky="w", padx=(2, 12), pady=3
        )
        ttk.Label(parent, textvariable=variable, style="Card.TLabel").grid(
            row=row, column=2, sticky="e", pady=3
        )

    def _build_calculator_result_panel(self, parent: ttk.Frame) -> None:
        self.calculator_result_vars = {
            key: tk.StringVar(value="—")
            for key in (
                "context",
                "up_plus",
                "up_minus",
                "down_plus",
                "down_minus",
                "input_delta",
                "recovered_vx",
                "branch",
                "constants",
            )
        }
        self._result_header(
            parent,
            "Raman Detuning Analysis",
            "Signed branch centers and inverse velocity reconstruction in the current experimental geometry.",
        )
        ttk.Label(
            parent,
            textvariable=self.calculator_result_vars["context"],
            style="Equation.TLabel",
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        branches = ttk.LabelFrame(
            parent, text="Forward model · resonance centers", style="Section.TLabelframe"
        )
        branches.pack(fill="x", pady=(0, 12))
        branches.columnconfigure((0, 1), weight=1)
        self._make_metric_card(branches, "δ(up,+)", "flying up · Δ > 0", self.calculator_result_vars["up_plus"], 0, 0)
        self._make_metric_card(branches, "δ(up,−)", "flying up · Δ < 0", self.calculator_result_vars["up_minus"], 0, 1)
        self._make_metric_card(branches, "δ(down,+)", "falling down · Δ > 0", self.calculator_result_vars["down_plus"], 1, 0)
        self._make_metric_card(branches, "δ(down,−)", "falling down · Δ < 0", self.calculator_result_vars["down_minus"], 1, 1)

        inverse = ttk.LabelFrame(
            parent, text="Inverse model · velocity solution", style="Section.TLabelframe"
        )
        inverse.pack(fill="x", pady=(0, 12))
        inverse.columnconfigure((0, 1), weight=1)
        self._make_metric_card(inverse, "δ(in)", "measured signed detuning", self.calculator_result_vars["input_delta"], 0, 0)
        self._make_metric_card(inverse, "v_x", "reconstructed transverse velocity", self.calculator_result_vars["recovered_vx"], 0, 1)
        ttk.Label(inverse, textvariable=self.calculator_result_vars["branch"], style="Muted.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", padx=6, pady=(5, 0)
        )

        ttk.Label(
            parent,
            textvariable=self.calculator_result_vars["constants"],
            style="Muted.TLabel",
            wraplength=850,
        ).pack(anchor="w")

    def _build_light_shift_result_panel(self, parent: ttk.Frame) -> None:
        self.light_shift_result_vars = {
            key: tk.StringVar(value="—")
            for key in (
                "transition",
                "measured_plus",
                "measured_minus",
                "measured_mean",
                "recoil",
                "light_shift",
                "doppler",
                "corrected_plus",
                "corrected_minus",
                "corrected_mean",
                "measured_coprop",
                "corrected_coprop",
            )
        }
        self._result_header(
            parent,
            "Differential AC Stark-shift Correction",
            "Common-mode extraction from the measured ±k_eff counter-propagating Raman pair.",
        )

        body = ttk.Panedwindow(parent, orient="horizontal")
        body.pack(fill="both", expand=True)

        analysis = ttk.Frame(body, style="Card.TFrame")
        body.add(analysis, weight=1)
        analysis.rowconfigure(0, weight=1)
        analysis.columnconfigure(0, weight=1)
        summary_frame = ttk.LabelFrame(
            analysis, text="Quantitative summary", style="Compact.TLabelframe"
        )
        summary_frame.grid(row=0, column=0, sticky="nsew")
        summary_frame.rowconfigure(0, weight=1)
        summary_frame.columnconfigure(0, weight=1)
        summary_figure = Figure(figsize=(4.2, 5.5), dpi=100, facecolor=CARD_BACKGROUND)
        self.light_shift_summary_ax = summary_figure.add_subplot(111)
        self.light_shift_summary_figure = summary_figure
        self.light_shift_summary_canvas = FigureCanvasTkAgg(summary_figure, master=summary_frame)
        self.light_shift_summary_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self._draw_empty_light_shift_summary()

        plot_frame = ttk.LabelFrame(
            body, text="Normalized counter-pro / co-pro spectrum", style="Compact.TLabelframe"
        )
        body.add(plot_frame, weight=2)
        plot_frame.rowconfigure(0, weight=1)
        plot_frame.columnconfigure(0, weight=1)
        figure = Figure(figsize=(2.2, 4.2), dpi=100, facecolor=CARD_BACKGROUND)
        self.light_shift_ax = figure.add_subplot(111)
        self.light_shift_figure = figure
        self.light_shift_canvas = FigureCanvasTkAgg(figure, master=plot_frame)
        self.light_shift_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        toolbar_frame = ttk.Frame(plot_frame, style="Card.TFrame")
        toolbar_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        self.light_shift_toolbar = NavigationToolbar2Tk(
            self.light_shift_canvas, toolbar_frame, pack_toolbar=False
        )
        self.light_shift_toolbar.update()
        self.light_shift_toolbar.grid(row=0, column=0, sticky="w")
        self.light_shift_cursor_var = tk.StringVar(
            value="Hover over the plot for coordinates · scroll to zoom · use the toolbar to pan, zoom, reset, or save."
        )
        ttk.Label(
            plot_frame,
            textvariable=self.light_shift_cursor_var,
            style="Muted.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(5, 0))
        ttk.Label(
            plot_frame,
            text="All three peak centers are calculated values; linewidths and relative amplitudes are illustrative.",
            style="Muted.TLabel",
        ).grid(row=3, column=0, sticky="w", pady=(2, 0))
        self.light_shift_canvas.mpl_connect("scroll_event", self._on_light_shift_scroll)
        self.light_shift_canvas.mpl_connect("motion_notify_event", self._on_light_shift_hover)
        self._draw_empty_light_shift_spectrum()

    def _build_calibration_result_panel(self, parent: ttk.Frame) -> None:
        self.calibration_result_vars = {
            key: tk.StringVar(value="—")
            for key in ("transition", "up_input", "down_input", "up_branch", "down_branch", "alpha", "vx")
        }
        self._result_header(
            parent,
            "Geometry and Velocity Calibration",
            "Joint reconstruction from signed flying-up and falling-down Raman resonance centers.",
        )
        observed = ttk.LabelFrame(parent, text="Measured scan centers", style="Section.TLabelframe")
        observed.pack(fill="x", pady=(0, 12))
        observed.columnconfigure((0, 1), weight=1)
        self._make_metric_card(observed, "δ(up)", "flying-up scan", self.calibration_result_vars["up_input"], 0, 0)
        self._make_metric_card(observed, "δ(down)", "falling-down scan", self.calibration_result_vars["down_input"], 0, 1)
        ttk.Label(observed, textvariable=self.calibration_result_vars["up_branch"], style="Muted.TLabel").grid(row=1, column=0, sticky="w", padx=6)
        ttk.Label(observed, textvariable=self.calibration_result_vars["down_branch"], style="Muted.TLabel").grid(row=1, column=1, sticky="w", padx=6)

        reconstructed = ttk.LabelFrame(parent, text="Reconstructed parameters", style="Section.TLabelframe")
        reconstructed.pack(fill="x", pady=(0, 12))
        reconstructed.columnconfigure((0, 1), weight=1)
        self._make_metric_card(reconstructed, "alpha", "Raman-beam angle", self.calibration_result_vars["alpha"], 0, 0)
        self._make_metric_card(reconstructed, "v_x", "transverse velocity", self.calibration_result_vars["vx"], 0, 1)

        equation = ttk.LabelFrame(parent, text="Reconstruction equations", style="Section.TLabelframe")
        equation.pack(fill="x")
        ttk.Label(
            equation,
            text="sin(alpha) = (U + D)/(2 k_eff v_z)     ·     v_x = (U − D)/(2 k_eff cos(alpha))",
            style="Equation.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            equation,
            textvariable=self.calibration_result_vars["transition"],
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(7, 0))

    def _draw_empty_light_shift_summary(self) -> None:
        ax = self.light_shift_summary_ax
        ax.clear()
        ax.set_axis_off()
        ax.text(
            0.5,
            0.54,
            "Run a light-shift correction\nto populate the quantitative summary.",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color=MUTED,
            fontsize=11,
            linespacing=1.5,
        )
        self.light_shift_summary_figure.subplots_adjust(
            left=0.03, right=0.97, bottom=0.03, top=0.97
        )
        self.light_shift_summary_canvas.draw_idle()

    def _draw_light_shift_summary(
        self,
        correction: LightShiftCorrectionResult,
        transition: str,
    ) -> None:
        ax = self.light_shift_summary_ax
        ax.clear()
        ax.set_axis_off()
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.0)

        def section(
            title: str,
            lines: list[str],
            top: float,
            height: float,
            accent: bool = False,
        ) -> None:
            face = "#eaf3f9" if accent else "#f7f9fb"
            edge = "#82abc4" if accent else "#d5e0e8"
            ax.add_patch(
                FancyBboxPatch(
                    (0.025, top - height),
                    0.95,
                    height,
                    boxstyle="round,pad=0.012,rounding_size=0.012",
                    facecolor=face,
                    edgecolor=edge,
                    linewidth=1.0,
                    transform=ax.transAxes,
                )
            )
            ax.text(
                0.06,
                top - 0.045,
                title.upper(),
                transform=ax.transAxes,
                ha="left",
                va="top",
                color=ACCENT if accent else MUTED,
                fontsize=9,
                fontweight="semibold",
            )
            line_y = top - 0.105
            spacing = (height - 0.13) / max(len(lines), 1)
            for index, line in enumerate(lines):
                ax.text(
                    0.07,
                    line_y - index * spacing,
                    line,
                    transform=ax.transAxes,
                    ha="left",
                    va="top",
                    color=INK,
                    fontsize=12,
                )

        measured_lines = [
            rf"$\delta_+^{{(\mathrm{{meas}})}}/2\pi = {correction.measured_delta_plus_khz:.6f}\ \mathrm{{kHz}}$",
            rf"$\delta_-^{{(\mathrm{{meas}})}}/2\pi = {correction.measured_delta_minus_khz:.6f}\ \mathrm{{kHz}}$",
            rf"$\bar{{\delta}}^{{(\mathrm{{meas}})}}/2\pi = {correction.measured_center_khz:.6f}\ \mathrm{{kHz}}$",
        ]
        extracted_lines = [
            rf"$D/2\pi = {correction.doppler_term_khz:+.6f}\ \mathrm{{kHz}}$",
            rf"$\delta_{{\mathrm{{AC}}}}/2\pi = {correction.light_shift_khz:+.6f}\ \mathrm{{kHz}}$",
            rf"$\delta_{{\mathrm{{co}}}}^{{(\mathrm{{meas}})}}/2\pi = {correction.measured_coprop_center_khz:+.6f}\ \mathrm{{kHz}}$",
            rf"$\delta_{{\mathrm{{co}}}}^{{(0)}}/2\pi = {correction.corrected_coprop_center_khz:.6f}\ \mathrm{{kHz}}$",
        ]
        corrected_lines = [
            rf"$\delta_+^{{(0)}}/2\pi = {correction.corrected_delta_plus_khz:.6f}\ \mathrm{{kHz}}$",
            rf"$\delta_-^{{(0)}}/2\pi = {correction.corrected_delta_minus_khz:.6f}\ \mathrm{{kHz}}$",
            rf"$s_{{\mathrm{{tr}}}} f_r = {correction.signed_recoil_center_khz:.6f}\ \mathrm{{kHz}}$",
        ]
        section("Measured counter-pro peaks", measured_lines, 0.985, 0.245)
        section("AC shift and co-pro center", extracted_lines, 0.715, 0.265, accent=True)
        section("Corrected counter-pro peaks", corrected_lines, 0.425, 0.245)

        transition_math = (
            r"F=1\rightarrow F=2"
            if transition == TRANSITION_F1_TO_F2
            else r"F=2\rightarrow F=1"
        )
        ax.text(
            0.04,
            0.125,
            rf"$\delta_{{\mathrm{{AC}}}}=\frac{{\delta_+^{{(\mathrm{{meas}})}}+\delta_-^{{(\mathrm{{meas}})}}}}{{2}}-s_{{\mathrm{{tr}}}}\omega_r$",
            transform=ax.transAxes,
            ha="left",
            va="center",
            color=INK,
            fontsize=11,
        )
        ax.text(
            0.04,
            0.045,
            rf"${transition_math}$   ·   common-shift model   ·   Zeeman/reference offsets neglected",
            transform=ax.transAxes,
            ha="left",
            va="center",
            color=MUTED,
            fontsize=8.5,
        )
        self.light_shift_summary_figure.subplots_adjust(
            left=0.02, right=0.98, bottom=0.02, top=0.98
        )
        self.light_shift_summary_canvas.draw_idle()

    def _draw_empty_light_shift_spectrum(self) -> None:
        ax = self.light_shift_ax
        ax.clear()
        ax.text(
            0.5,
            0.54,
            r"Enter $\delta_+$ and $\delta_-$, then run the correction",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color=MUTED,
            fontsize=11,
        )
        ax.text(
            0.5,
            0.43,
            "The measured and light-shift-corrected spectra will be compared here.",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color=MUTED,
            fontsize=10,
        )
        ax.set_axis_off()
        self.light_shift_figure.subplots_adjust(left=0.17, right=0.97, bottom=0.14, top=0.92)
        self.light_shift_canvas.draw_idle()

    def _on_light_shift_scroll(self, event: object) -> None:
        if getattr(event, "inaxes", None) is not self.light_shift_ax:
            return
        xdata = getattr(event, "xdata", None)
        ydata = getattr(event, "ydata", None)
        if xdata is None or ydata is None:
            return
        scale = 0.8 if getattr(event, "button", None) == "up" else 1.25
        x_left, x_right = self.light_shift_ax.get_xlim()
        y_bottom, y_top = self.light_shift_ax.get_ylim()
        self.light_shift_ax.set_xlim(
            xdata - (xdata - x_left) * scale,
            xdata + (x_right - xdata) * scale,
        )
        self.light_shift_ax.set_ylim(
            ydata - (ydata - y_bottom) * scale,
            ydata + (y_top - ydata) * scale,
        )
        self.light_shift_canvas.draw_idle()

    def _on_light_shift_hover(self, event: object) -> None:
        if getattr(event, "inaxes", None) is not self.light_shift_ax:
            self.light_shift_cursor_var.set(
                "Hover for coordinates · scroll to zoom · toolbar: home, pan, box zoom, save."
            )
            return
        xdata = getattr(event, "xdata", None)
        ydata = getattr(event, "ydata", None)
        if xdata is None or ydata is None:
            return
        self.light_shift_cursor_var.set(
            f"Cursor   δ / 2π = {xdata:.3f} kHz   ·   normalized probability = {ydata:.4f}"
        )

    def _draw_light_shift_spectrum(
        self, correction: LightShiftCorrectionResult
    ) -> None:
        measured = np.array(
            [
                correction.measured_delta_minus_khz,
                correction.measured_coprop_center_khz,
                correction.measured_delta_plus_khz,
            ],
            dtype=float,
        )
        corrected = np.array(
            [
                correction.corrected_delta_minus_khz,
                correction.corrected_coprop_center_khz,
                correction.corrected_delta_plus_khz,
            ],
            dtype=float,
        )
        splitting = max(abs(float(np.diff(np.sort(measured))[0])), 1.0)
        linewidth = max(0.025 * splitting, 1.0)
        lower = min(float(np.min(measured)), float(np.min(corrected))) - 5.0 * linewidth
        upper = max(float(np.max(measured)), float(np.max(corrected))) + 5.0 * linewidth
        frequency = np.linspace(lower, upper, 1800)

        def normalized_triplet(centers: np.ndarray) -> np.ndarray:
            relative_amplitudes = np.array([1.0, 0.78, 1.0])
            signal = sum(
                amplitude * np.exp(-0.5 * ((frequency - center) / linewidth) ** 2)
                for center, amplitude in zip(centers, relative_amplitudes, strict=True)
            )
            maximum = float(np.max(signal))
            return signal / maximum if maximum > 0.0 else signal

        measured_signal = normalized_triplet(measured)
        corrected_signal = normalized_triplet(corrected)
        ax = self.light_shift_ax
        ax.clear()
        ax.plot(
            frequency,
            measured_signal,
            color=CURVE_B,
            linewidth=2.0,
            linestyle="--",
            label="Measured spectrum",
        )
        ax.plot(
            frequency,
            corrected_signal,
            color=CURVE_A,
            linewidth=2.2,
            label="After light-shift correction",
        )
        for center in measured:
            ax.axvline(center, color=CURVE_B, alpha=0.24, linewidth=1.0, linestyle="--")
        for center in corrected:
            ax.axvline(center, color=CURVE_A, alpha=0.24, linewidth=1.0)

        measured_mean = correction.measured_coprop_center_khz
        corrected_mean = correction.corrected_coprop_center_khz
        ax.annotate(
            "",
            xy=(corrected_mean, 1.075),
            xytext=(measured_mean, 1.075),
            arrowprops={"arrowstyle": "<->", "color": ACCENT, "linewidth": 1.4},
            annotation_clip=False,
        )
        ax.text(
            0.5 * (measured_mean + corrected_mean),
            1.105,
            rf"$\delta_{{\mathrm{{AC}}}}={correction.light_shift_khz:+.3f}\ \mathrm{{kHz}}$",
            ha="center",
            va="bottom",
            color=ACCENT,
            fontsize=9,
        )
        ax.set_xlabel(r"Raman detuning, $\delta/2\pi$ (kHz)", fontsize=11)
        ax.set_ylabel("Normalized transfer probability", fontsize=11)
        ax.set_ylim(-0.03, 1.18)
        ax.grid(True, color="#d9e2ea", linewidth=0.7, alpha=0.75)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(loc="upper center", frameon=False, ncol=1, fontsize=10)
        ax.tick_params(colors=INK, labelsize=10)
        ax.xaxis.label.set_color(INK)
        ax.yaxis.label.set_color(INK)
        self.light_shift_figure.subplots_adjust(left=0.17, right=0.97, bottom=0.14, top=0.92)
        self.light_shift_canvas.draw_idle()
        self.light_shift_toolbar.update()

    def _build_detuning_constants_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(
            parent,
            text="Experimental Constants",
            style="Section.TLabelframe",
        )
        section.pack(fill="x", padx=4, pady=(4, 14))
        self._add_detuning_numeric_field(
            section,
            "vz_m_s",
            "Vertical velocity vz",
            "m/s",
            "Fixed longitudinal launch velocity used by the original detuning script.",
        )
        self._add_detuning_numeric_field(
            section,
            "alpha_deg",
            "Beam angle alpha",
            "deg",
            "Angle between the Raman beam and the z-axis. This is the quantity targeted by calibration.",
        )
        self._add_detuning_numeric_field(
            section,
            "laser_wavelength_nm",
            "Laser wavelength",
            "nm",
            "Laser wavelength used to build k and keff.",
        )
        self._add_detuning_numeric_field(
            section,
            "recoil_frequency_khz",
            "Recoil frequency",
            "kHz",
            "Two-photon recoil frequency entering the detuning formulas.",
        )

    def _build_detuning_calculator_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(
            parent,
            text="Detuning Calculator",
            style="Section.TLabelframe",
        )
        section.pack(fill="x", padx=4, pady=(0, 14))

        mode_row = ttk.Frame(section, style="Card.TFrame")
        mode_row.pack(fill="x")
        ttk.Radiobutton(
            mode_row,
            text="vx -> Detuning",
            variable=self.detuning_vars["mode"],
            value="vx2detuning",
            command=self._update_detuning_mode_label,
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            mode_row,
            text="Detuning -> vx",
            variable=self.detuning_vars["mode"],
            value="detuning2vx",
            command=self._update_detuning_mode_label,
        ).pack(side="left")

        input_frame = ttk.Frame(section, style="Card.TFrame")
        input_frame.pack(fill="x", pady=(10, 0))
        ttk.Label(
            input_frame,
            textvariable=self.detuning_vars["input_label"],
            style="Field.TLabel",
            width=18,
        ).pack(side="left")
        ttk.Entry(
            input_frame,
            textvariable=self.detuning_vars["input_value"],
            width=16,
        ).pack(side="left")

        motion_frame = ttk.Frame(section, style="Card.TFrame")
        motion_frame.pack(fill="x", pady=(10, 0))
        ttk.Label(motion_frame, text="Motion mode", style="Field.TLabel", width=18).pack(
            side="left"
        )
        ttk.Combobox(
            motion_frame,
            textvariable=self.detuning_vars["motion"],
            values=MOTION_CHOICES,
            state="readonly",
            width=14,
        ).pack(side="left")

        transition_frame = ttk.Frame(section, style="Card.TFrame")
        transition_frame.pack(fill="x", pady=(10, 0))
        ttk.Label(
            transition_frame, text="Transition", style="Field.TLabel", width=18
        ).pack(side="left")
        ttk.Combobox(
            transition_frame,
            textvariable=self.detuning_vars["transition"],
            values=TRANSITION_CHOICES,
            state="readonly",
            width=10,
        ).pack(side="left")

        ttk.Button(
            section,
            text="Calculate Detuning Tool",
            style="Primary.TButton",
            command=self.calculate_detuning_tool,
        ).pack(fill="x", pady=(12, 0))
        ttk.Label(
            section,
            text=(
                "Forward mode reports all four physical detuning branches. In inverse mode, "
                "the selected motion direction and the sign of the detuning determine the formula."
            ),
            style="Muted.TLabel",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

    def _build_detuning_calibration_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(
            parent,
            text="Alpha / vx Calibration",
            style="Section.TLabelframe",
        )
        section.pack(fill="x", padx=4, pady=(0, 10))

        self._add_detuning_numeric_field(
            section,
            "calibration_up_khz",
            "Flying-up scan result",
            "kHz",
            "Signed resonance detuning obtained from the flying-up scan.",
        )
        self._add_detuning_numeric_field(
            section,
            "calibration_down_khz",
            "Falling-down scan result",
            "kHz",
            "Signed resonance detuning obtained from the falling-down scan.",
        )

        transition_frame = ttk.Frame(section, style="Card.TFrame")
        transition_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(
            transition_frame, text="Transition", style="Field.TLabel", width=18
        ).pack(side="left")
        ttk.Combobox(
            transition_frame,
            textvariable=self.detuning_vars["calibration_transition"],
            values=TRANSITION_CHOICES,
            state="readonly",
            width=10,
        ).pack(side="left")

        ttk.Button(
            section,
            text="Run Calibration",
            style="Primary.TButton",
            command=self.run_detuning_calibration,
        ).pack(fill="x", pady=(0, 8))
        self.apply_calibration_button = ttk.Button(
            section,
            text="Apply Calibration to Constants",
            style="Secondary.TButton",
            command=self.apply_last_detuning_calibration,
        )
        self.apply_calibration_button.pack(fill="x")
        ttk.Label(
            section,
            text=(
                "Calibration assumes the flying-up and falling-down scan results correspond "
                "to the same transition direction. The sign of each entered detuning selects "
                "the Delta>0 or Delta<0 branch automatically. The current alpha field is not "
                "used as an input during calibration; it is reconstructed from the scan results."
            ),
            style="Muted.TLabel",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

    def _build_light_shift_correction_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(
            parent,
            text="Light-shift Correction",
            style="Section.TLabelframe",
        )
        section.pack(fill="x", padx=4, pady=(0, 14))

        self._add_detuning_numeric_field(
            section,
            "light_shift_delta_plus_khz",
            "Measured delta+ center",
            "kHz",
            "Fitted center of the +keff counter-propagating Raman peak.",
        )
        self._add_detuning_numeric_field(
            section,
            "light_shift_delta_minus_khz",
            "Measured delta- center",
            "kHz",
            "Fitted center of the -keff counter-propagating Raman peak.",
        )

        transition_frame = ttk.Frame(section, style="Card.TFrame")
        transition_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(
            transition_frame, text="Transition", style="Field.TLabel", width=18
        ).pack(side="left")
        ttk.Combobox(
            transition_frame,
            textvariable=self.detuning_vars["light_shift_transition"],
            values=TRANSITION_CHOICES,
            state="readonly",
            width=10,
        ).pack(side="left")

        ttk.Button(
            section,
            text="Calculate and Remove Light Shift",
            style="Primary.TButton",
            command=self.calculate_light_shift_correction,
        ).pack(fill="x")
        ttk.Label(
            section,
            text=(
                "Assumes both peaks have the same differential light shift. The corrected "
                "centers retain the signed recoil term; Zeeman and frequency-zero offsets "
                "are ignored."
            ),
            style="Muted.TLabel",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

    def _add_detuning_numeric_field(
        self,
        parent: ttk.LabelFrame,
        key: str,
        label: str,
        unit: str,
        description: str,
    ) -> None:
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill="x", pady=(0, 12))
        ttk.Label(frame, text=label, style="Field.TLabel").pack(anchor="w")
        row = ttk.Frame(frame, style="Card.TFrame")
        row.pack(fill="x", pady=(4, 0))
        ttk.Entry(row, textvariable=self.detuning_vars[key], width=16).pack(side="left")
        ttk.Label(row, text=unit, style="Muted.TLabel").pack(side="left", padx=(8, 0))
        ttk.Label(
            frame,
            text=description,
            style="Muted.TLabel",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

    def _update_detuning_mode_label(self) -> None:
        if str(self.detuning_vars["mode"].get()) == "vx2detuning":
            self.detuning_vars["input_label"].set("vx (mm/s):")
            return
        self.detuning_vars["input_label"].set("Detuning (kHz):")

    def _set_readonly_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _build_control_sections(self) -> None:
        self._build_preset_section()
        self._build_primary_inputs()
        self._build_advanced_inputs()
        self._build_numerics_inputs()
        self._build_action_section()

    def _configure_temperature_linkage(self) -> None:
        self.variables["transverse_temperature_uK"].trace_add(
            "write", self._sync_longitudinal_temperature_from_transverse
        )
        self.variables["use_separate_longitudinal_temperature"].trace_add(
            "write", self._update_longitudinal_temperature_entry_state
        )

    def _sync_longitudinal_temperature_from_transverse(
        self, *_args: object
    ) -> None:
        if bool(self.variables["use_separate_longitudinal_temperature"].get()):
            return
        transverse_value = str(self.variables["transverse_temperature_uK"].get())
        if str(self.variables["longitudinal_temperature_uK"].get()) != transverse_value:
            self.variables["longitudinal_temperature_uK"].set(transverse_value)

    def _update_longitudinal_temperature_entry_state(
        self, *_args: object
    ) -> None:
        entry = self.field_entries.get("longitudinal_temperature_uK")
        if entry is None:
            return
        separate = bool(self.variables["use_separate_longitudinal_temperature"].get())
        if separate:
            entry.configure(state="normal")
            return
        self._sync_longitudinal_temperature_from_transverse()
        entry.configure(state="disabled")

    def _build_preset_section(self) -> None:
        section = ttk.LabelFrame(
            self.controls_parent,
            text="Presets",
            style="Section.TLabelframe",
        )
        section.pack(fill="x", padx=4, pady=(4, 14))

        ttk.Label(
            section,
            text="Preset library",
            style="Field.TLabel",
        ).pack(anchor="w")

        row = ttk.Frame(section, style="Card.TFrame")
        row.pack(fill="x", pady=(6, 0))
        self.preset_combobox = ttk.Combobox(
            row,
            textvariable=self.preset_name_var,
            state="readonly",
            values=self._preset_names(),
            width=28,
        )
        self.preset_combobox.pack(side="left", fill="x", expand=True)
        self.preset_combobox.bind("<<ComboboxSelected>>", self._on_preset_selected)

        ttk.Button(
            row,
            text="Apply",
            style="Primary.TButton",
            command=self.apply_selected_preset,
        ).pack(side="left", padx=(10, 0))

        ttk.Label(
            section,
            textvariable=self.preset_info_var,
            style="Muted.TLabel",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(8, 10))

        actions = ttk.Frame(section, style="Card.TFrame")
        actions.pack(fill="x")
        self.save_preset_button = ttk.Button(
            actions,
            text="Save to Selected Preset",
            style="Secondary.TButton",
            command=self.save_to_selected_preset,
        )
        self.save_preset_button.pack(fill="x", pady=(0, 8))
        self.save_as_preset_button = ttk.Button(
            actions,
            text="Save as New Preset",
            style="Secondary.TButton",
            command=self.save_as_new_preset,
        )
        self.save_as_preset_button.pack(fill="x", pady=(0, 8))
        self.delete_preset_button = ttk.Button(
            actions,
            text="Delete Local Preset Copy",
            style="Secondary.TButton",
            command=self.delete_selected_preset,
        )
        self.delete_preset_button.pack(fill="x")

    def _build_primary_inputs(self) -> None:
        section = ttk.LabelFrame(
            self.controls_parent,
            text="Primary Inputs",
            style="Section.TLabelframe",
        )
        section.pack(fill="x", padx=4, pady=(4, 14))

        self._add_numeric_field(
            section,
            key="transverse_temperature_uK",
            label="Transverse temperature",
            unit="uK",
            description=(
                "Temperature associated with the transverse velocity spread sigma_v,T. "
                "This quantity drives the cloud expansion and the radial convolution with the Raman beams."
            ),
        )
        self._add_boolean_field(
            section,
            key="use_separate_longitudinal_temperature",
            label="Use a separate longitudinal temperature",
            description=(
                "Enable an independent longitudinal temperature for sigma_v,L. "
                "When disabled, the longitudinal temperature is locked to the transverse value."
            ),
        )
        self._add_numeric_field(
            section,
            key="longitudinal_temperature_uK",
            label="Longitudinal temperature",
            unit="uK",
            description=(
                "Temperature associated with the longitudinal velocity spread sigma_v,L. "
                "This quantity enters the velocity-selection distribution f(vL)."
            ),
        )
        self._add_numeric_field(
            section,
            key="desacc_mhz",
            label="Large Raman detuning desacc / 2pi",
            unit="MHz",
            description=(
                "Single-photon detuning measured from the excited-state manifold. "
                "The original Mathematica script uses -1000 MHz."
            ),
        )
        self._add_numeric_field(
            section,
            key="p1_mw",
            label="Beam power P1",
            unit="mW",
            description="Optical power of Raman beam P1 entering the Gaussian intensity model.",
        )
        self._add_numeric_field(
            section,
            key="p2_mw",
            label="Beam power P2",
            unit="mW",
            description="Optical power of Raman beam P2 entering the Gaussian intensity model.",
        )
        self._add_numeric_field(
            section,
            key="w0_mm",
            label="Beam waist w0",
            unit="mm",
            description=(
                "1/e^2 Gaussian beam radius used for both Raman beams in the translated model."
            ),
        )
        self._add_numeric_field(
            section,
            key="tau_min_us",
            label="tau minimum",
            unit="us",
            description="Lower bound of the Raman pulse-duration sweep displayed in the Rabi plot.",
        )
        self._add_numeric_field(
            section,
            key="tau_max_us",
            label="tau maximum",
            unit="us",
            description=(
                "Upper bound of the Raman pulse-duration sweep displayed in the Rabi plot."
            ),
        )
        self._add_integer_field(
            section,
            key="tau_points",
            label="Number of tau samples",
            unit="pts",
            description=(
                "Sampling density for both plots. Larger values yield smoother curves and a longer runtime."
            ),
        )

    def _build_advanced_inputs(self) -> None:
        section = ttk.LabelFrame(
            self.controls_parent,
            text="Advanced Model Parameters",
            style="Section.TLabelframe",
        )
        section.pack(fill="x", padx=4, pady=(0, 14))

        self._add_numeric_field(
            section,
            key="expansion_time_ms",
            label="Expansion time T before Raman pulse",
            unit="ms",
            description=(
                "Free-expansion time used inside the Raman integral, corresponding to T in Ptrans[T, tau, d, w0, attn]."
            ),
        )
        self._add_numeric_field(
            section,
            key="initial_cloud_sigma_mm",
            label="Initial cloud size sigma_r(0)",
            unit="mm",
            description=(
                "Initial transverse root-mean-square cloud size. The Mathematica default is 5 mm."
            ),
        )
        self._add_numeric_field(
            section,
            key="two_photon_detuning_khz",
            label="Two-photon detuning d / 2pi",
            unit="kHz",
            description=(
                "Residual Raman detuning used in delta = k_eff * v_L - d. Keep zero to match the original plot."
            ),
        )
        self._add_numeric_field(
            section,
            key="attenuation",
            label="Attenuation factor",
            unit="a.u.",
            description=(
                "Multiplicative attenuation applied to the effective Raman Rabi frequency as in the Mathematica model."
            ),
        )
        self._add_numeric_field(
            section,
            key="gain",
            label="Coupling gain G",
            unit="a.u.",
            description=(
                "Dimensionless gain factor retained from the original script. Leave at 1 unless a calibrated correction is needed."
            ),
        )

    def _build_numerics_inputs(self) -> None:
        section = ttk.LabelFrame(
            self.controls_parent,
            text="Numerical Controls",
            style="Section.TLabelframe",
        )
        section.pack(fill="x", padx=4, pady=(0, 14))

        self._add_integer_field(
            section,
            key="radial_points",
            label="Radial grid points",
            unit="pts",
            description="Number of radial quadrature points between r = 0 and the selected waist cutoff.",
        )
        self._add_integer_field(
            section,
            key="velocity_points",
            label="Velocity grid points",
            unit="pts",
            description=(
                "Number of longitudinal velocity quadrature points spanning the selected sigma cutoff."
            ),
        )
        self._add_numeric_field(
            section,
            key="radial_cutoff_waists",
            label="Radial cutoff",
            unit="x w0",
            description="Maximum radial integration boundary expressed in multiples of the beam waist.",
        )
        self._add_numeric_field(
            section,
            key="velocity_cutoff_sigma",
            label="Velocity cutoff",
            unit="x sigma",
            description="Maximum absolute longitudinal velocity included in the integral in units of sigma_v,L.",
        )

    def _build_action_section(self) -> None:
        section = ttk.LabelFrame(
            self.controls_parent,
            text="Interface Notes",
            style="Section.TLabelframe",
        )
        section.pack(fill="x", padx=4, pady=(0, 10))

        ttk.Label(
            section,
            text=(
                "Units follow experimental practice: temperature in uK, powers in mW, "
                "beam waist and cloud size in mm, and pulse duration in us."
            ),
            style="Muted.TLabel",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(12, 0))
        ttk.Label(
            section,
            text=(
                "Top-right controls handle simulation execution, result locking, and CSV export. "
                "Locked results remain visible while you run new parameter sets."
            ),
            style="Muted.TLabel",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

    def _build_plot_tab(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=0)

        figure_frame = ttk.Frame(parent, style="Card.TFrame")
        figure_frame.grid(row=0, column=0, sticky="nsew")
        figure_frame.rowconfigure(0, weight=1)
        figure_frame.columnconfigure(0, weight=1)

        figure = Figure(figsize=(9.8, 7.4), dpi=100, facecolor="#f9fbfd")
        self.ax_rabi = figure.add_subplot(211)
        self.ax_cloud = figure.add_subplot(212)
        figure.subplots_adjust(left=0.09, right=0.97, top=0.96, bottom=0.09, hspace=0.33)
        self.figure = figure

        canvas = FigureCanvasTkAgg(figure, master=figure_frame)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        toolbar = NavigationToolbar2Tk(canvas, figure_frame, pack_toolbar=False)
        toolbar.update()
        toolbar.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.canvas = canvas
        self.toolbar = toolbar

        sidebar = ttk.Frame(parent, style="Card.TFrame", padding=(14, 0, 0, 0))
        sidebar.grid(row=0, column=1, sticky="ns")

        overlay = ttk.LabelFrame(
            sidebar,
            text="Simulation Stack",
            style="Section.TLabelframe",
        )
        overlay.pack(fill="x", pady=(0, 12))
        ttk.Label(
            overlay,
            textvariable=self.overlay_status_var,
            style="Muted.TLabel",
            wraplength=260,
            justify="left",
        ).pack(anchor="w")

        interaction = ttk.LabelFrame(
            sidebar,
            text="Plot Interaction",
            style="Section.TLabelframe",
        )
        interaction.pack(fill="x", pady=(0, 12))

        ttk.Checkbutton(
            interaction,
            text="Auto-scale Rabi y-axis",
            variable=self.auto_scale_rabi_var,
            command=self._refresh_plot_only,
            style="TCheckbutton",
        ).pack(anchor="w")
        ttk.Label(
            interaction,
            text=(
                "When enabled, the Rabi-probability axis automatically zooms to the "
                "observed signal level instead of remaining fixed at 0 to 1."
            ),
            style="Muted.TLabel",
            wraplength=260,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        ttk.Button(
            interaction,
            text="Reset Plot View",
            style="Secondary.TButton",
            command=self.reset_plot_view,
        ).pack(fill="x", pady=(0, 8))
        ttk.Button(
            interaction,
            text="Clear Plot Markers",
            style="Secondary.TButton",
            command=self.clear_plot_markers,
        ).pack(fill="x")

        cursor = ttk.LabelFrame(
            sidebar,
            text="Cursor Readout",
            style="Section.TLabelframe",
        )
        cursor.pack(fill="x")
        ttk.Label(
            cursor,
            textvariable=self.plot_hover_var,
            style="Muted.TLabel",
            wraplength=260,
            justify="left",
        ).pack(anchor="w")
        ttk.Label(
            cursor,
            textvariable=self.plot_marker_var,
            style="Muted.TLabel",
            wraplength=260,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

        self.canvas.mpl_connect("motion_notify_event", self._on_plot_hover)
        self.canvas.mpl_connect("button_press_event", self._on_plot_click)

    def _build_derived_tab(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        self.derived_text = tk.Text(
            parent,
            wrap="word",
            background=CARD_BACKGROUND,
            foreground=INK,
            relief="flat",
            font=("Segoe UI", 10),
            padx=8,
            pady=8,
        )
        self.derived_text.grid(row=0, column=0, sticky="nsew")
        self.derived_text.insert(
            "1.0",
            "Run a simulation to populate the derived quantities panel.",
        )
        self.derived_text.configure(state="disabled")

    def _build_notes_tab(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        notes = tk.Text(
            parent,
            wrap="word",
            background=CARD_BACKGROUND,
            foreground=INK,
            relief="flat",
            font=("Segoe UI", 10),
            padx=8,
            pady=8,
        )
        notes.grid(row=0, column=0, sticky="nsew")
        notes.insert(
            "1.0",
            (
                "Model scope\n"
                "\n"
                "This application translates the Mathematica script Raman.txt into a "
                "Python model for two-photon Raman transitions in an atomic interferometer. "
                "The transition probability follows the same structure as Ptrans[T, tau, d, w0, attn] in the original file.\n"
                "\n"
                "Key assumptions\n"
                "\n"
                "1. Gaussian Raman beams share the same waist w0.\n"
                "2. The atomic cloud has a Gaussian transverse spatial profile governed by the transverse temperature.\n"
                "3. The longitudinal velocity distribution is Gaussian and governed by the longitudinal temperature.\n"
                "4. The atom-cloud expansion plot tracks sigma_r(T) = sqrt(sigma_r(0)^2 + sigma_v,T^2 T^2) over the free-expansion time axis.\n"
                "5. The Rabi-oscillation plot uses a fixed expansion time T selected in the advanced settings.\n"
                "\n"
                "Translated equations\n"
                "\n"
                "I_i(r) = 2 P_i / (pi w0^2) * exp(-2 r^2 / w0^2)\n"
                "Omega_eff(r) = gamma^2 * G / attn * sqrt(I1 I2) / (2 Isat) * "
                "[5 / (24 desacc) + 3 / (24 (desacc + delta2))] / 2\n"
                "Omega_R(r, v) = sqrt(Omega_eff(r)^2 + (k_eff v - d)^2)\n"
                "P(T, tau) = integral integral 2 pi r f(v) h(r, T) "
                "[Omega_eff / Omega_R * sin(Omega_R tau / 2)]^2 dv dr\n"
                "\n"
                "Default behavior inherited from Raman.txt\n"
                "\n"
                "The starting values match the Mathematica file whenever a direct translation is possible. "
                "In particular, the default temperature is chosen so that the transverse velocity spread "
                "equals 2.65 v_rec. By default the longitudinal temperature is linked to the transverse one, "
                "but it can be released and edited independently.\n"
            ),
        )
        notes.configure(state="disabled")

    def _add_numeric_field(
        self,
        parent: ttk.LabelFrame,
        key: str,
        label: str,
        unit: str,
        description: str,
    ) -> None:
        variable = tk.StringVar()
        self.variables[key] = variable

        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill="x", pady=(0, 12))

        ttk.Label(frame, text=label, style="Field.TLabel").pack(anchor="w")
        row = ttk.Frame(frame, style="Card.TFrame")
        row.pack(fill="x", pady=(4, 0))
        entry = ttk.Entry(row, textvariable=variable, width=16)
        entry.pack(side="left")
        self.field_entries[key] = entry
        ttk.Label(row, text=unit, style="Muted.TLabel").pack(side="left", padx=(8, 0))
        ttk.Label(
            frame,
            text=description,
            style="Muted.TLabel",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

    def _add_integer_field(
        self,
        parent: ttk.LabelFrame,
        key: str,
        label: str,
        unit: str,
        description: str,
    ) -> None:
        self._add_numeric_field(parent, key, label, unit, description)

    def _add_boolean_field(
        self,
        parent: ttk.LabelFrame,
        key: str,
        label: str,
        description: str,
    ) -> None:
        variable = tk.BooleanVar()
        self.variables[key] = variable

        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill="x", pady=(0, 12))
        ttk.Checkbutton(
            frame,
            text=label,
            variable=variable,
            style="TCheckbutton",
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text=description,
            style="Muted.TLabel",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

    def _default_field_values(self) -> dict[str, object]:
        return dict(DEFAULT_FIELD_VALUES)

    def _preset_names(self) -> list[str]:
        names = list(BUNDLED_PRESETS.keys())
        for name in sorted(self.user_presets.keys()):
            if name not in names:
                names.append(name)
        return names

    def _load_user_presets(self) -> dict[str, dict[str, object]]:
        if not PRESET_FILE.exists():
            return {}

        try:
            payload = json.loads(PRESET_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

        if not isinstance(payload, dict):
            return {}

        cleaned: dict[str, dict[str, object]] = {}
        for name, values in payload.items():
            if not isinstance(name, str) or not isinstance(values, dict):
                continue
            cleaned_values: dict[str, object] = {}
            for key, value in values.items():
                if key not in DEFAULT_FIELD_VALUES:
                    continue
                normalized = self._normalize_field_value(key, value)
                if normalized is not None:
                    cleaned_values[key] = normalized
            if cleaned_values:
                cleaned[name] = cleaned_values
        return cleaned

    def _save_user_presets(self) -> None:
        serialized = {
            name: {
                key: self._normalize_field_value(key, value)
                for key, value in values.items()
                if self._normalize_field_value(key, value) is not None
            }
            for name, values in self.user_presets.items()
        }
        PRESET_FILE.write_text(
            json.dumps(serialized, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _normalize_field_value(self, key: str, value: object) -> object | None:
        try:
            if key in BOOLEAN_FIELDS:
                return bool(value)
            if key in INTEGER_FIELDS:
                return int(value)
            return float(value)
        except (TypeError, ValueError):
            return None

    def _format_field_value(self, key: str, value: object) -> str:
        if key in BOOLEAN_FIELDS:
            raise ValueError(f"Boolean field {key} should not be formatted as text.")
        if key in INTEGER_FIELDS:
            return str(int(value))
        return f"{float(value):.6f}"

    def _apply_field_values(self, values: dict[str, object]) -> None:
        for key, default_value in self._default_field_values().items():
            variable = self.variables[key]
            applied = values.get(key, default_value)
            if isinstance(variable, tk.BooleanVar):
                variable.set(bool(applied))
            else:
                variable.set(self._format_field_value(key, applied))

    def _composed_preset_values(self, name: str) -> dict[str, object]:
        values = self._default_field_values()
        if name in BUNDLED_PRESETS:
            values.update(BUNDLED_PRESETS[name])
        if name in self.user_presets:
            values.update(self.user_presets[name])
        return values

    def _preset_source_label(self, name: str) -> str:
        if name in BUNDLED_PRESETS and name in self.user_presets:
            return "Bundled preset with a locally saved override."
        if name in self.user_presets:
            return "User-defined preset stored in presets.json."
        return "Bundled preset shipped with the application."

    def _preset_summary(self, name: str) -> str:
        values = self._composed_preset_values(name)
        note = BUNDLED_PRESET_NOTES.get(name, "Custom preset.")
        return (
            f"{self._preset_source_label(name)} {note} "
            f"P1 = {float(values['p1_mw']):.3f} mW, "
            f"P2 = {float(values['p2_mw']):.3f} mW, "
            f"w0 = {float(values['w0_mm']):.3f} mm, "
            f"T = {float(values['expansion_time_ms']):.3f} ms, "
            f"desacc / 2pi = {float(values['desacc_mhz']):.3f} MHz."
        )

    def _refresh_preset_selector(self, selected_name: str | None = None) -> None:
        names = self._preset_names()
        self.preset_combobox.configure(values=names)
        current = selected_name or self.preset_name_var.get()
        if current not in names:
            current = names[0]
        self.preset_name_var.set(current)
        self.preset_info_var.set(self._preset_summary(current))

    def _on_preset_selected(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        self.preset_info_var.set(self._preset_summary(self.preset_name_var.get()))

    def apply_selected_preset(self) -> None:
        name = self.preset_name_var.get()
        self._apply_field_values(self._composed_preset_values(name))
        self.preset_info_var.set(self._preset_summary(name))
        self.status_var.set(f"Applied preset '{name}'.")
        self.run_simulation()

    def _current_field_snapshot(self) -> dict[str, object]:
        params = self._read_parameters()
        params.validate()
        return {
            "transverse_temperature_uK": params.transverse_temperature_uK,
            "use_separate_longitudinal_temperature": (
                params.use_separate_longitudinal_temperature
            ),
            "longitudinal_temperature_uK": params.longitudinal_temperature_uK,
            "desacc_mhz": params.desacc_mhz,
            "p1_mw": params.p1_mw,
            "p2_mw": params.p2_mw,
            "w0_mm": params.w0_mm,
            "tau_min_us": params.tau_min_us,
            "tau_max_us": params.tau_max_us,
            "tau_points": params.tau_points,
            "expansion_time_ms": params.expansion_time_ms,
            "initial_cloud_sigma_mm": params.initial_cloud_sigma_mm,
            "two_photon_detuning_khz": params.two_photon_detuning_khz,
            "attenuation": params.attenuation,
            "gain": params.gain,
            "radial_points": params.radial_points,
            "velocity_points": params.velocity_points,
            "radial_cutoff_waists": params.radial_cutoff_waists,
            "velocity_cutoff_sigma": params.velocity_cutoff_sigma,
        }

    def save_to_selected_preset(self) -> None:
        try:
            snapshot = self._current_field_snapshot()
        except Exception as exc:
            messagebox.showerror(
                "Preset save blocked",
                f"Current inputs must be valid before saving a preset.\n\n{exc}",
            )
            return

        name = self.preset_name_var.get().strip()
        if not name:
            messagebox.showerror("Missing preset name", "Select or enter a preset name first.")
            return

        self.user_presets[name] = snapshot
        self._save_user_presets()
        self._refresh_preset_selector(name)
        self.status_var.set(f"Saved the current parameters to preset '{name}'.")

    def save_as_new_preset(self) -> None:
        try:
            snapshot = self._current_field_snapshot()
        except Exception as exc:
            messagebox.showerror(
                "Preset save blocked",
                f"Current inputs must be valid before saving a preset.\n\n{exc}",
            )
            return

        name = simpledialog.askstring(
            "Save as new preset",
            "Preset name:",
            initialvalue=self.preset_name_var.get(),
            parent=self.root,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            messagebox.showerror("Invalid preset name", "Preset names must not be empty.")
            return
        if name in self._preset_names() and not messagebox.askyesno(
            "Overwrite preset?",
            f"A preset named '{name}' already exists. Overwrite it?",
            parent=self.root,
        ):
            return

        self.user_presets[name] = snapshot
        self._save_user_presets()
        self._refresh_preset_selector(name)
        self.status_var.set(f"Saved a new preset named '{name}'.")

    def delete_selected_preset(self) -> None:
        name = self.preset_name_var.get()
        if name not in self.user_presets:
            messagebox.showinfo(
                "Preset not removable",
                "Only locally saved presets or local overrides can be deleted.",
                parent=self.root,
            )
            return

        if not messagebox.askyesno(
            "Delete preset",
            f"Delete the local preset copy '{name}' from presets.json?",
            parent=self.root,
        ):
            return

        del self.user_presets[name]
        self._save_user_presets()
        fallback = name if name in BUNDLED_PRESETS else "Original Raman.txt Defaults"
        self._refresh_preset_selector(fallback)
        self.status_var.set(f"Deleted the local preset copy for '{name}'.")

    def _format_compact_number(self, value: float) -> str:
        magnitude = abs(value)
        if magnitude >= 100:
            return f"{value:.0f}"
        if magnitude >= 10:
            return f"{value:.1f}".rstrip("0").rstrip(".")
        if magnitude >= 1:
            return f"{value:.2f}".rstrip("0").rstrip(".")
        return f"{value:.3f}".rstrip("0").rstrip(".")

    def _parameter_label_fields(self, params: RamanSimulationParameters) -> dict[str, str]:
        if params.use_separate_longitudinal_temperature:
            temperature_label = (
                "Tperp/Tlong "
                f"{self._format_compact_number(params.transverse_temperature_uK)}/"
                f"{self._format_compact_number(params.longitudinal_temperature_uK)} uK"
            )
        else:
            temperature_label = (
                f"Temp {self._format_compact_number(params.transverse_temperature_uK)} uK"
            )
        return {
            "power": (
                "P "
                f"{self._format_compact_number(params.p1_mw)}/"
                f"{self._format_compact_number(params.p2_mw)} mW"
            ),
            "waist": f"w0 {self._format_compact_number(params.w0_mm)} mm",
            "time": f"T {self._format_compact_number(params.expansion_time_ms)} ms",
            "detuning": f"Delta {self._format_compact_number(params.desacc_mhz)} MHz",
            "temperature": temperature_label,
            "two_photon": (
                f"d {self._format_compact_number(params.two_photon_detuning_khz)} kHz"
            ),
        }

    def _parameter_sets_match(
        self, first: RamanSimulationParameters, second: RamanSimulationParameters
    ) -> bool:
        return all(
            (
                getattr(first, key) == getattr(second, key)
                if key in BOOLEAN_FIELDS or key in INTEGER_FIELDS
                else np.isclose(
                    float(getattr(first, key)),
                    float(getattr(second, key)),
                    rtol=0.0,
                    atol=1e-12,
                )
            )
            for key in DEFAULT_FIELD_VALUES
        )

    def _build_display_runs(
        self,
        current_params: RamanSimulationParameters,
        current_result: RamanSimulationResult,
    ) -> list[DisplaySimulation]:
        max_cloud_time_s = max(
            [current_result.cloud_time_s[-1]]
            + [snapshot.result.cloud_time_s[-1] for snapshot in self.locked_results]
        )
        _, cloud_unit = choose_display_time_axis(np.array([max_cloud_time_s]))
        self.cloud_time_unit_for_plot = cloud_unit
        cloud_scale = TIME_UNIT_FACTORS[cloud_unit]

        runs: list[DisplaySimulation] = []
        for index, snapshot in enumerate(self.locked_results, start=1):
            runs.append(
                DisplaySimulation(
                    identifier=f"Lock {index}",
                    params=snapshot.params,
                    result=snapshot.result,
                    color=LOCKED_RESULT_COLORS[(index - 1) % len(LOCKED_RESULT_COLORS)],
                    is_current=False,
                    legend_label="",
                    cloud_time_plot=snapshot.result.cloud_time_s * cloud_scale,
                )
            )

        runs.append(
            DisplaySimulation(
                identifier="Current",
                params=current_params,
                result=current_result,
                color=CURVE_A,
                is_current=True,
                legend_label="",
                cloud_time_plot=current_result.cloud_time_s * cloud_scale,
            )
        )

        field_order = ["power", "waist", "time", "detuning", "temperature", "two_photon"]
        formatted_fields = [self._parameter_label_fields(run.params) for run in runs]
        varying_fields = [
            field
            for field in field_order
            if len({parts[field] for parts in formatted_fields}) > 1
        ]
        if not varying_fields:
            varying_fields = ["power", "waist", "time"]
        varying_fields = varying_fields[:4]

        for run, parts in zip(runs, formatted_fields):
            summary = ", ".join(parts[field] for field in varying_fields)
            run.legend_label = f"{run.identifier}: {summary}"
        return runs

    def _update_overlay_status(self) -> None:
        locked_count = len(self.locked_results)
        if locked_count == 0:
            self.overlay_status_var.set(
                "Displaying the current simulation result only. Lock it before scanning a new parameter set."
            )
            return
        plural = "curve" if locked_count == 1 else "curves"
        self.overlay_status_var.set(
            f"Displaying the current result plus {locked_count} locked reference {plural}. "
            "Legends list only the parameters that differ across displayed runs."
        )

    def lock_current_result(self) -> None:
        if self.last_params is None or self.last_result is None:
            messagebox.showinfo(
                "No result to lock",
                "Run a simulation before locking a reference curve.",
                parent=self.root,
            )
            return

        for snapshot in self.locked_results:
            if self._parameter_sets_match(snapshot.params, self.last_params):
                self.status_var.set(
                    "The current parameter set is already present in the locked reference stack."
                )
                return

        self.locked_results.append(
            SimulationSnapshot(params=self.last_params, result=self.last_result)
        )
        self._update_overlay_status()
        self._refresh_plot_only()
        self.status_var.set(
            f"Locked the current simulation result as reference curve {len(self.locked_results)}."
        )

    def clear_locked_results(self) -> None:
        if not self.locked_results:
            self.status_var.set("There are no locked reference curves to clear.")
            return

        self.locked_results.clear()
        self._update_overlay_status()
        self._refresh_plot_only()
        self.status_var.set("Cleared all locked reference curves.")

    def _read_detuning_constants(self) -> DetuningConstants:
        constants = DetuningConstants(
            vz_m_s=float(str(self.detuning_vars["vz_m_s"].get()).strip()),
            alpha_deg=float(str(self.detuning_vars["alpha_deg"].get()).strip()),
            laser_wavelength_m=float(
                str(self.detuning_vars["laser_wavelength_nm"].get()).strip()
            )
            * 1e-9,
            recoil_frequency_khz=float(
                str(self.detuning_vars["recoil_frequency_khz"].get()).strip()
            ),
        )
        constants.validate()
        return constants

    def calculate_detuning_tool(self) -> None:
        try:
            constants = self._read_detuning_constants()
            input_value = float(str(self.detuning_vars["input_value"].get()).strip())
        except Exception as exc:
            messagebox.showerror(
                "Detuning input error",
                f"Please review the detuning-page inputs.\n\n{exc}",
                parent=self.root,
            )
            return

        mode = str(self.detuning_vars["mode"].get())
        motion = str(self.detuning_vars["motion"].get())
        transition = str(self.detuning_vars["transition"].get())

        if mode == "vx2detuning":
            detunings = compute_detuning_khz(input_value, transition, constants)
            lines = [
                "Raman detuning results",
                "",
                f"Input vx: {input_value:.6f} mm/s",
                f"Transition: {transition}",
                (
                    f"Constants: vz = {constants.vz_m_s:.6f} m/s, "
                    f"alpha = {constants.alpha_deg:.6f} deg, "
                    f"lambda = {constants.laser_wavelength_m * 1e9:.6f} nm, "
                    f"wr / 2pi = {constants.recoil_frequency_khz:.6f} kHz"
                ),
                "",
            ]
            for label, value in detunings.items():
                lines.append(f"{label}: {value:.6f} kHz")
            content = "\n".join(lines)
            self.detuning_vars["calculator_result"].set(content)
            self.calculator_result_vars["context"].set(
                f"Forward solution   ·   vₓ = {input_value:.6f} mm/s   ·   {transition}"
            )
            self.calculator_result_vars["up_plus"].set(
                f"{detunings[f'{FLYING_UP}, Δ>0']:.6f} kHz"
            )
            self.calculator_result_vars["up_minus"].set(
                f"{detunings[f'{FLYING_UP}, Δ<0']:.6f} kHz"
            )
            self.calculator_result_vars["down_plus"].set(
                f"{detunings[f'{FALLING_DOWN}, Δ>0']:.6f} kHz"
            )
            self.calculator_result_vars["down_minus"].set(
                f"{detunings[f'{FALLING_DOWN}, Δ<0']:.6f} kHz"
            )
            self.calculator_result_vars["input_delta"].set("—")
            self.calculator_result_vars["recovered_vx"].set("—")
            self.calculator_result_vars["branch"].set(
                "Inverse solution is populated when Detuning → vx is selected."
            )
            self.calculator_result_vars["constants"].set(
                f"Model constants   v_z = {constants.vz_m_s:.6f} m/s   ·   "
                f"α = {constants.alpha_deg:.6f}°   ·   λ = {constants.laser_wavelength_m * 1e9:.3f} nm   ·   "
                f"fᵣ = {constants.recoil_frequency_khz:.6f} kHz"
            )
            self.detuning_results_notebook.select(self.detuning_calculator_tab)
            self.status_var.set("Computed the Raman detuning branches from vx.")
            return

        try:
            inversion = compute_vx_from_detuning_auto(
                input_value, motion, transition, constants
            )
        except Exception as exc:
            messagebox.showerror(
                "Detuning inversion error",
                str(exc),
                parent=self.root,
            )
            return

        content = "\n".join(
            [
                "Velocity inversion result",
                "",
                f"Input detuning: {input_value:.6f} kHz",
                f"Motion mode: {motion}",
                f"Transition: {transition}",
                f"Recovered vx: {inversion.vx_mm_s:.6f} mm/s",
                f"Formula used: {inversion.used_case}",
                "",
                (
                    f"Constants: vz = {constants.vz_m_s:.6f} m/s, "
                    f"alpha = {constants.alpha_deg:.6f} deg, "
                    f"lambda = {constants.laser_wavelength_m * 1e9:.6f} nm, "
                    f"wr / 2pi = {constants.recoil_frequency_khz:.6f} kHz"
                ),
            ]
        )
        self.detuning_vars["calculator_result"].set(content)
        self.calculator_result_vars["context"].set(
            f"Inverse solution   ·   {motion}   ·   {transition}"
        )
        self.calculator_result_vars["input_delta"].set(f"{input_value:.6f} kHz")
        self.calculator_result_vars["recovered_vx"].set(
            f"{inversion.vx_mm_s:.6f} mm/s"
        )
        self.calculator_result_vars["branch"].set(
            f"Selected physical branch: {inversion.used_case}"
        )
        for key in ("up_plus", "up_minus", "down_plus", "down_minus"):
            self.calculator_result_vars[key].set("—")
        self.calculator_result_vars["constants"].set(
            f"Model constants   v_z = {constants.vz_m_s:.6f} m/s   ·   "
            f"α = {constants.alpha_deg:.6f}°   ·   λ = {constants.laser_wavelength_m * 1e9:.3f} nm   ·   "
            f"fᵣ = {constants.recoil_frequency_khz:.6f} kHz"
        )
        self.detuning_results_notebook.select(self.detuning_calculator_tab)
        self.status_var.set("Recovered vx from the signed Raman detuning.")

    def calculate_light_shift_correction(self) -> None:
        try:
            constants = self._read_detuning_constants()
            measured_delta_plus_khz = float(
                str(self.detuning_vars["light_shift_delta_plus_khz"].get()).strip()
            )
            measured_delta_minus_khz = float(
                str(self.detuning_vars["light_shift_delta_minus_khz"].get()).strip()
            )
            transition = str(self.detuning_vars["light_shift_transition"].get())
            correction = compute_light_shift_correction(
                measured_delta_plus_khz,
                measured_delta_minus_khz,
                transition,
                constants,
            )
        except Exception as exc:
            messagebox.showerror(
                "Light-shift input error",
                f"Please review the measured peak centers and detuning constants.\n\n{exc}",
                parent=self.root,
            )
            return

        content = "\n".join(
            [
                "Light-shift correction result",
                "",
                f"Transition: {transition}",
                f"Measured delta+ center: {correction.measured_delta_plus_khz:.6f} kHz",
                f"Measured delta- center: {correction.measured_delta_minus_khz:.6f} kHz",
                f"Measured pair mean: {correction.measured_center_khz:.6f} kHz",
                f"Signed recoil center: {correction.signed_recoil_center_khz:.6f} kHz",
                "",
                f"Extracted light shift: {correction.light_shift_khz:+.6f} kHz",
                f"Doppler term (half splitting): {correction.doppler_term_khz:+.6f} kHz",
                f"Measured co-pro center: {correction.measured_coprop_center_khz:+.6f} kHz",
                "",
                "Peak centers after removing light shift",
                f"Corrected delta+: {correction.corrected_delta_plus_khz:.6f} kHz",
                f"Corrected delta-: {correction.corrected_delta_minus_khz:.6f} kHz",
                f"Corrected co-pro center: {correction.corrected_coprop_center_khz:.6f} kHz",
                (
                    "Corrected pair mean: "
                    f"{0.5 * (correction.corrected_delta_plus_khz + correction.corrected_delta_minus_khz):.6f} kHz"
                ),
                "",
                "Model used:",
                "delta+ = +D + signed recoil + light shift",
                "delta- = -D + signed recoil + light shift",
                "",
                (
                    "This quick correction assumes a common light shift for the two peaks "
                    "and intentionally neglects Zeeman and frequency-reference offsets."
                ),
            ]
        )
        self.detuning_vars["light_shift_result"].set(content)
        self.light_shift_result_vars["transition"].set(
            f"{transition}   ·   common-shift model   ·   Zeeman/reference offsets neglected"
        )
        self.light_shift_result_vars["measured_plus"].set(
            f"{correction.measured_delta_plus_khz:.6f} kHz"
        )
        self.light_shift_result_vars["measured_minus"].set(
            f"{correction.measured_delta_minus_khz:.6f} kHz"
        )
        self.light_shift_result_vars["measured_mean"].set(
            f"{correction.measured_center_khz:.6f} kHz"
        )
        self.light_shift_result_vars["recoil"].set(
            f"{correction.signed_recoil_center_khz:.6f} kHz"
        )
        self.light_shift_result_vars["light_shift"].set(
            f"{correction.light_shift_khz:+.6f} kHz"
        )
        self.light_shift_result_vars["doppler"].set(
            f"{correction.doppler_term_khz:+.6f} kHz"
        )
        self.light_shift_result_vars["corrected_plus"].set(
            f"{correction.corrected_delta_plus_khz:.6f} kHz"
        )
        self.light_shift_result_vars["corrected_minus"].set(
            f"{correction.corrected_delta_minus_khz:.6f} kHz"
        )
        self.light_shift_result_vars["corrected_mean"].set(
            f"{0.5 * (correction.corrected_delta_plus_khz + correction.corrected_delta_minus_khz):.6f} kHz"
        )
        self.light_shift_result_vars["measured_coprop"].set(
            f"{correction.measured_coprop_center_khz:+.6f} kHz"
        )
        self.light_shift_result_vars["corrected_coprop"].set(
            f"{correction.corrected_coprop_center_khz:.6f} kHz"
        )
        self._draw_light_shift_summary(correction, transition)
        self._draw_light_shift_spectrum(correction)
        self.detuning_results_notebook.select(self.detuning_light_shift_tab)
        self.status_var.set("Extracted and removed the common Raman light shift.")

    def run_detuning_calibration(self) -> None:
        try:
            constants = DetuningConstants(
                vz_m_s=float(str(self.detuning_vars["vz_m_s"].get()).strip()),
                alpha_deg=0.0,
                laser_wavelength_m=float(
                    str(self.detuning_vars["laser_wavelength_nm"].get()).strip()
                )
                * 1e-9,
                recoil_frequency_khz=float(
                    str(self.detuning_vars["recoil_frequency_khz"].get()).strip()
                ),
            )
            constants.validate()
            flying_up_detuning_khz = float(
                str(self.detuning_vars["calibration_up_khz"].get()).strip()
            )
            falling_down_detuning_khz = float(
                str(self.detuning_vars["calibration_down_khz"].get()).strip()
            )
            transition = str(self.detuning_vars["calibration_transition"].get())
            calibration = calibrate_alpha_and_vx_from_scans(
                flying_up_detuning_khz,
                falling_down_detuning_khz,
                transition,
                constants,
            )
        except Exception as exc:
            messagebox.showerror(
                "Calibration error",
                f"Could not calibrate alpha and vx from the provided scan results.\n\n{exc}",
                parent=self.root,
            )
            return

        self.last_detuning_calibration = calibration
        content = "\n".join(
            [
                "Calibration result",
                "",
                f"Transition: {transition}",
                f"Flying-up scan input: {flying_up_detuning_khz:.6f} kHz",
                f"Falling-down scan input: {falling_down_detuning_khz:.6f} kHz",
                f"Detected flying-up branch: {calibration.flying_up_case}",
                f"Detected falling-down branch: {calibration.falling_down_case}",
                "",
                f"Recovered alpha: {calibration.alpha_deg:.6f} deg",
                f"Recovered vx: {calibration.vx_mm_s:.6f} mm/s",
                "",
                (
                    "The reconstruction uses the same detuning model as the original script, "
                    "with the sign of each entered detuning selecting the Delta>0 or Delta<0 branch."
                ),
            ]
        )
        self.detuning_vars["calibration_result"].set(content)
        self.calibration_result_vars["transition"].set(
            f"Transition: {transition}   ·   branch signs selected automatically from the scan centers"
        )
        self.calibration_result_vars["up_input"].set(
            f"{flying_up_detuning_khz:.6f} kHz"
        )
        self.calibration_result_vars["down_input"].set(
            f"{falling_down_detuning_khz:.6f} kHz"
        )
        self.calibration_result_vars["up_branch"].set(
            f"Branch: {calibration.flying_up_case}"
        )
        self.calibration_result_vars["down_branch"].set(
            f"Branch: {calibration.falling_down_case}"
        )
        self.calibration_result_vars["alpha"].set(
            f"{calibration.alpha_deg:.6f}°"
        )
        self.calibration_result_vars["vx"].set(
            f"{calibration.vx_mm_s:.6f} mm/s"
        )
        self.detuning_results_notebook.select(self.detuning_calibration_tab)
        self.status_var.set("Calibrated alpha and vx from flying-up and falling-down scan results.")

    def apply_last_detuning_calibration(self) -> None:
        if self.last_detuning_calibration is None:
            messagebox.showinfo(
                "No calibration available",
                "Run the detuning calibration first.",
                parent=self.root,
            )
            return

        self.detuning_vars["alpha_deg"].set(f"{self.last_detuning_calibration.alpha_deg:.6f}")
        self.detuning_vars["input_value"].set(f"{self.last_detuning_calibration.vx_mm_s:.6f}")
        self.detuning_vars["mode"].set("vx2detuning")
        self._update_detuning_mode_label()
        self.status_var.set(
            "Applied the calibrated alpha to the detuning constants and copied the calibrated vx into the calculator input."
        )

    def reset_to_defaults(self) -> None:
        self._apply_field_values(self._default_field_values())
        self._refresh_preset_selector("Original Raman.txt Defaults")
        self.status_var.set("Defaults restored from Raman.txt and its translated assumptions.")

    def export_last_result(self) -> None:
        if self.last_result is None:
            messagebox.showinfo(
                "No result available",
                "Run a simulation before exporting data.",
            )
            return

        destination = filedialog.asksaveasfilename(
            title="Export Raman simulation data",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="raman_simulation.csv",
        )
        if not destination:
            return

        with Path(destination).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "tau_us",
                    "transition_probability",
                    "cloud_time_s",
                    f"cloud_time_{self.last_result.cloud_time_unit}",
                    "cloud_sigma_mm",
                ]
            )
            for tau_us, probability, cloud_time_s, cloud_time_display, cloud_sigma in zip(
                self.last_result.tau_us,
                self.last_result.transition_probability,
                self.last_result.cloud_time_s,
                self.last_result.cloud_time_display,
                self.last_result.cloud_radius_mm,
            ):
                writer.writerow(
                    [tau_us, probability, cloud_time_s, cloud_time_display, cloud_sigma]
                )

        self.status_var.set(f"Exported the last simulation result to {destination}.")

    def _read_parameters(self) -> RamanSimulationParameters:
        return RamanSimulationParameters(
            transverse_temperature_uK=self._as_float("transverse_temperature_uK"),
            use_separate_longitudinal_temperature=self._as_bool(
                "use_separate_longitudinal_temperature"
            ),
            longitudinal_temperature_uK=self._as_float("longitudinal_temperature_uK"),
            desacc_mhz=self._as_float("desacc_mhz"),
            p1_mw=self._as_float("p1_mw"),
            p2_mw=self._as_float("p2_mw"),
            w0_mm=self._as_float("w0_mm"),
            tau_min_us=self._as_float("tau_min_us"),
            tau_max_us=self._as_float("tau_max_us"),
            tau_points=self._as_int("tau_points"),
            expansion_time_ms=self._as_float("expansion_time_ms"),
            initial_cloud_sigma_mm=self._as_float("initial_cloud_sigma_mm"),
            two_photon_detuning_khz=self._as_float("two_photon_detuning_khz"),
            attenuation=self._as_float("attenuation"),
            gain=self._as_float("gain"),
            radial_points=self._as_int("radial_points"),
            velocity_points=self._as_int("velocity_points"),
            radial_cutoff_waists=self._as_float("radial_cutoff_waists"),
            velocity_cutoff_sigma=self._as_float("velocity_cutoff_sigma"),
        )

    def _as_float(self, key: str) -> float:
        raw = str(self.variables[key].get()).strip()
        return float(raw)

    def _as_int(self, key: str) -> int:
        raw = str(self.variables[key].get()).strip()
        return int(raw)

    def _as_bool(self, key: str) -> bool:
        return bool(self.variables[key].get())

    def run_simulation(self) -> None:
        if self.is_running:
            self.status_var.set("A simulation is already running. Please wait for it to finish.")
            return

        try:
            params = self._read_parameters()
            params.validate()
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            self.status_var.set("Input validation failed. Review the current parameter values.")
            return
        except Exception as exc:
            messagebox.showerror("Input parsing error", str(exc))
            self.status_var.set("Could not parse the current input fields.")
            return

        self.status_var.set("Running Raman integral and cloud-expansion calculation...")
        self._set_running_state(True)

        worker = threading.Thread(
            target=self._run_simulation_worker,
            args=(params,),
            daemon=True,
        )
        worker.start()

    def _run_simulation_worker(self, params: RamanSimulationParameters) -> None:
        try:
            result = simulate_rabi_oscillation(params)
        except Exception as exc:
            self.root.after(0, lambda: self._handle_simulation_error(str(exc)))
            return

        self.root.after(0, lambda: self._finish_simulation(params, result))

    def _handle_simulation_error(self, message: str) -> None:
        self._set_running_state(False)
        self.status_var.set("Simulation failed. Inspect the message and adjust the inputs.")
        messagebox.showerror("Simulation error", message)

    def _finish_simulation(
        self,
        params: RamanSimulationParameters,
        result: RamanSimulationResult,
    ) -> None:
        self._set_running_state(False)
        self.last_params = params
        self.last_result = result
        self._update_overlay_status()
        self._update_plots(params, result)
        self._update_derived_text(params, result)
        self.status_var.set(
            "Simulation complete. Curves and derived quantities have been updated."
        )

    def _set_running_state(self, running: bool) -> None:
        self.is_running = running
        self._refresh_header_action_state()
        state = "disabled" if running else "normal"
        self.save_preset_button.configure(state=state)
        self.save_as_preset_button.configure(state=state)
        self.delete_preset_button.configure(state=state)
        self.preset_combobox.configure(state="disabled" if running else "readonly")
        self.root.configure(cursor="watch" if running else "")

    def _refresh_plot_only(self) -> None:
        if self.last_params is not None and self.last_result is not None:
            self._update_plots(self.last_params, self.last_result)

    def reset_plot_view(self) -> None:
        if not self.plot_default_limits:
            return
        for axis_name, axis in (("rabi", self.ax_rabi), ("cloud", self.ax_cloud)):
            limits = self.plot_default_limits.get(axis_name)
            if limits is None:
                continue
            xlim, ylim = limits
            axis.set_xlim(*xlim)
            axis.set_ylim(*ylim)
        self.canvas.draw_idle()
        self.plot_marker_var.set(
            "Plot view reset to the latest auto-generated limits."
        )

    def clear_plot_markers(self) -> None:
        for marker_set in self.marker_artists.values():
            marker = marker_set.get("marker")
            annotation = marker_set.get("annotation")
            if marker is not None:
                marker.set_visible(False)
            if annotation is not None:
                annotation.set_visible(False)
        self.canvas.draw_idle()
        self.plot_marker_var.set(
            "Plot markers cleared. Click inside a plot to pin a new marker."
        )

    def _toolbar_mode_active(self) -> bool:
        return bool(self.toolbar and getattr(self.toolbar, "mode", ""))

    def _nearest_point(
        self, x_data: np.ndarray, y_data: np.ndarray, x_value: float
    ) -> tuple[int, float, float]:
        index = int(np.abs(x_data - x_value).argmin())
        return index, float(x_data[index]), float(y_data[index])

    def _nearest_display_run_point(
        self, plot_name: str, x_value: float, y_value: float
    ) -> tuple[DisplaySimulation, int, float, float] | None:
        if not self.display_runs_cache:
            return None

        axis = self.ax_rabi if plot_name == "rabi" else self.ax_cloud
        x_limits = axis.get_xlim()
        y_limits = axis.get_ylim()
        x_span = max(abs(x_limits[1] - x_limits[0]), 1e-12)
        y_span = max(abs(y_limits[1] - y_limits[0]), 1e-12)

        best_match: tuple[float, DisplaySimulation, int, float, float] | None = None
        for run in self.display_runs_cache:
            if plot_name == "rabi":
                x_data = run.result.tau_us
                y_data = run.result.transition_probability
            else:
                x_data = run.cloud_time_plot
                y_data = run.result.cloud_radius_mm

            index, x_nearest, y_nearest = self._nearest_point(x_data, y_data, x_value)
            score = ((x_nearest - x_value) / x_span) ** 2 + (
                (y_nearest - y_value) / y_span
            ) ** 2
            if best_match is None or score < best_match[0]:
                best_match = (score, run, index, x_nearest, y_nearest)

        if best_match is None:
            return None
        return best_match[1], best_match[2], best_match[3], best_match[4]

    def _hide_crosshairs(self) -> None:
        for lines in self.crosshair_lines.values():
            vertical, horizontal = lines
            vertical.set_visible(False)
            horizontal.set_visible(False)

    def _initialize_plot_interaction_artists(self) -> None:
        self.crosshair_lines = {
            "rabi": (
                self.ax_rabi.axvline(0.0, color="#6e8091", linewidth=0.8, linestyle=":"),
                self.ax_rabi.axhline(0.0, color="#6e8091", linewidth=0.8, linestyle=":"),
            ),
            "cloud": (
                self.ax_cloud.axvline(0.0, color="#8a745d", linewidth=0.8, linestyle=":"),
                self.ax_cloud.axhline(0.0, color="#8a745d", linewidth=0.8, linestyle=":"),
            ),
        }
        for lines in self.crosshair_lines.values():
            lines[0].set_visible(False)
            lines[1].set_visible(False)

        self.marker_artists = {
            "rabi": {
                "marker": self.ax_rabi.plot(
                    [],
                    [],
                    marker="o",
                    markersize=6,
                    color=MARKER_A,
                    linestyle="None",
                    zorder=6,
                )[0],
                "annotation": self.ax_rabi.annotate(
                    "",
                    xy=(0.0, 0.0),
                    xytext=(12, 10),
                    textcoords="offset points",
                    color=MARKER_A,
                    fontsize=9,
                    bbox={
                        "boxstyle": "round,pad=0.25",
                        "fc": "#eef5fb",
                        "ec": "#c5d7e7",
                    },
                    arrowprops={"arrowstyle": "->", "color": MARKER_A, "lw": 0.8},
                ),
            },
            "cloud": {
                "marker": self.ax_cloud.plot(
                    [],
                    [],
                    marker="o",
                    markersize=6,
                    color=MARKER_B,
                    linestyle="None",
                    zorder=6,
                )[0],
                "annotation": self.ax_cloud.annotate(
                    "",
                    xy=(0.0, 0.0),
                    xytext=(12, 10),
                    textcoords="offset points",
                    color=MARKER_B,
                    fontsize=9,
                    bbox={
                        "boxstyle": "round,pad=0.25",
                        "fc": "#fcf2eb",
                        "ec": "#ead1bf",
                    },
                    arrowprops={"arrowstyle": "->", "color": MARKER_B, "lw": 0.8},
                ),
            },
        }
        for marker_set in self.marker_artists.values():
            marker_set["marker"].set_visible(False)
            marker_set["annotation"].set_visible(False)

    def _update_hover_readout(self, plot_name: str, x_value: float, y_value: float) -> None:
        nearest = self._nearest_display_run_point(plot_name, x_value, y_value)
        if nearest is None:
            return
        run, index, x_nearest, y_nearest = nearest

        if plot_name == "rabi":
            self.plot_hover_var.set(
                f"Rabi plot | {run.identifier} | "
                f"nearest sample #{index + 1}: tau = {x_nearest:.3f} us, P = {y_nearest:.6f}."
            )
            return

        self.plot_hover_var.set(
            f"Cloud plot | {run.identifier} | "
            f"nearest sample #{index + 1}: time = {x_nearest:.3f} {self.cloud_time_unit_for_plot}, "
            f"sigma_r = {y_nearest:.6f} mm."
        )

    def _on_plot_hover(self, event: object) -> None:
        if self.last_result is None:
            return
        if self._toolbar_mode_active():
            self._hide_crosshairs()
            self.canvas.draw_idle()
            return

        inaxes = getattr(event, "inaxes", None)
        xdata = getattr(event, "xdata", None)
        ydata = getattr(event, "ydata", None)
        if inaxes not in (self.ax_rabi, self.ax_cloud) or xdata is None or ydata is None:
            self._hide_crosshairs()
            self.canvas.draw_idle()
            self.plot_hover_var.set(
                "Move the cursor over a curve to inspect the nearest sample."
            )
            return

        axis_name = "rabi" if inaxes is self.ax_rabi else "cloud"
        self._hide_crosshairs()
        vertical, horizontal = self.crosshair_lines[axis_name]
        vertical.set_xdata([xdata, xdata])
        horizontal.set_ydata([ydata, ydata])
        vertical.set_visible(True)
        horizontal.set_visible(True)
        self._update_hover_readout(axis_name, float(xdata), float(ydata))
        self.canvas.draw_idle()

    def _on_plot_click(self, event: object) -> None:
        if self.last_result is None or self._toolbar_mode_active():
            return

        if getattr(event, "dblclick", False):
            self.reset_plot_view()
            return

        inaxes = getattr(event, "inaxes", None)
        button = getattr(event, "button", None)
        button_value = getattr(button, "value", button)
        xdata = getattr(event, "xdata", None)
        ydata = getattr(event, "ydata", None)
        if (
            button_value != 1
            or inaxes not in (self.ax_rabi, self.ax_cloud)
            or xdata is None
            or ydata is None
        ):
            return

        axis_name = "rabi" if inaxes is self.ax_rabi else "cloud"
        if axis_name == "rabi":
            nearest = self._nearest_display_run_point(axis_name, float(xdata), float(ydata))
            if nearest is None:
                return
            run, _, x_nearest, y_nearest = nearest
            label = f"{run.identifier}\ntau = {x_nearest:.3f} us\nP = {y_nearest:.6f}"
        else:
            nearest = self._nearest_display_run_point(axis_name, float(xdata), float(ydata))
            if nearest is None:
                return
            run, _, x_nearest, y_nearest = nearest
            label = (
                f"{run.identifier}\n"
                f"time = {x_nearest:.3f} {self.cloud_time_unit_for_plot}\n"
                f"sigma_r = {y_nearest:.6f} mm"
            )

        marker_set = self.marker_artists[axis_name]
        marker = marker_set["marker"]
        annotation = marker_set["annotation"]
        marker.set_data([x_nearest], [y_nearest])
        marker.set_visible(True)
        annotation.xy = (x_nearest, y_nearest)
        annotation.set_text(label)
        annotation.set_visible(True)
        self.canvas.draw_idle()
        self.plot_marker_var.set(
            f"Pinned marker on the {axis_name} plot for {run.identifier} at x = {x_nearest:.3f}."
        )

    def _set_rabi_axis_limits(self, display_runs: list[DisplaySimulation]) -> None:
        x_min = min(float(run.result.tau_us[0]) for run in display_runs)
        x_max = max(float(run.result.tau_us[-1]) for run in display_runs)
        self.ax_rabi.set_xlim(x_min, x_max)
        if not self.auto_scale_rabi_var.get():
            self.ax_rabi.set_ylim(-0.02, 1.02)
            return

        y_max = max(float(np.max(run.result.transition_probability)) for run in display_runs)
        y_min = min(float(np.min(run.result.transition_probability)) for run in display_runs)
        if y_max >= 0.75:
            self.ax_rabi.set_ylim(-0.02, 1.02)
            return

        upper_margin = max(0.01, 0.18 * max(y_max, 0.02))
        lower_margin = max(0.002, 0.08 * max(y_max, 0.02))
        lower = y_min - lower_margin
        if y_min >= 0.0:
            lower = -lower_margin
        upper = max(0.06, y_max + upper_margin)
        upper = min(1.02, upper)
        if upper - lower < 0.03:
            upper = lower + 0.03
        self.ax_rabi.set_ylim(lower, upper)

    def _set_cloud_axis_limits(self, display_runs: list[DisplaySimulation]) -> None:
        self.ax_cloud.set_xlim(
            0.0, max(float(run.cloud_time_plot[-1]) for run in display_runs)
        )
        y_min = min(float(np.min(run.result.cloud_radius_mm)) for run in display_runs)
        y_max = max(float(np.max(run.result.cloud_radius_mm)) for run in display_runs)
        span = y_max - y_min
        margin = max(2e-6, 0.15 * span, 0.0002 * max(y_max, 1.0))
        self.ax_cloud.set_ylim(y_min - margin, y_max + margin)

    def _record_default_plot_limits(self) -> None:
        self.plot_default_limits = {
            "rabi": (self.ax_rabi.get_xlim(), self.ax_rabi.get_ylim()),
            "cloud": (self.ax_cloud.get_xlim(), self.ax_cloud.get_ylim()),
        }

    def _update_plots(
        self, params: RamanSimulationParameters, result: RamanSimulationResult
    ) -> None:
        self.ax_rabi.clear()
        self.ax_cloud.clear()
        display_runs = self._build_display_runs(params, result)
        self.display_runs_cache = display_runs

        show_legend = len(display_runs) > 1
        for run in display_runs:
            self.ax_rabi.plot(
                run.result.tau_us,
                run.result.transition_probability,
                color=run.color,
                linewidth=2.4 if run.is_current else 1.8,
                linestyle="-" if run.is_current else "--",
                alpha=1.0 if run.is_current else 0.9,
                label=run.legend_label,
                zorder=4 if run.is_current else 2,
            )
            if run.is_current:
                self.ax_rabi.fill_between(
                    run.result.tau_us,
                    run.result.transition_probability,
                    color=run.color,
                    alpha=0.10 if show_legend else 0.12,
                    zorder=1,
                )
        self.ax_rabi.set_title(
            "Raman Rabi Oscillation",
            color=INK,
            fontsize=13,
            fontfamily=PLOT_TITLE_FONT,
        )
        self.ax_rabi.set_xlabel("Pulse duration tau (us)")
        self.ax_rabi.set_ylabel("Transition probability")
        self.ax_rabi.grid(True, color="#d7e0ea", linewidth=0.8)
        self.ax_rabi.xaxis.set_major_locator(MaxNLocator(nbins=6))
        self.ax_rabi.yaxis.set_major_locator(MaxNLocator(nbins=6))
        self._set_rabi_axis_limits(display_runs)

        if result.pi_pulse_time_us < self.ax_rabi.get_xlim()[1]:
            y_top = self.ax_rabi.get_ylim()[1]
            self.ax_rabi.axvline(
                result.pi_pulse_time_us,
                color="#59758d",
                linestyle="--",
                linewidth=1.2,
                alpha=0.9,
            )
            self.ax_rabi.text(
                result.pi_pulse_time_us,
                y_top - 0.04 * (self.ax_rabi.get_ylim()[1] - self.ax_rabi.get_ylim()[0]),
                "estimated pi pulse",
                rotation=90,
                va="top",
                ha="right",
                color="#59758d",
                fontsize=9,
            )
        if show_legend:
            self.ax_rabi.legend(
                loc="best",
                fontsize=8,
                frameon=True,
                facecolor="#ffffff",
                edgecolor="#d0dce8",
            )

        for run in display_runs:
            self.ax_cloud.plot(
                run.cloud_time_plot,
                run.result.cloud_radius_mm,
                color=run.color,
                linewidth=2.3 if run.is_current else 1.8,
                linestyle="-" if run.is_current else "--",
                alpha=1.0 if run.is_current else 0.9,
                label=run.legend_label,
                zorder=4 if run.is_current else 2,
            )
            if run.is_current:
                self.ax_cloud.fill_between(
                    run.cloud_time_plot,
                    run.result.cloud_radius_mm,
                    color=run.color,
                    alpha=0.08 if show_legend else 0.12,
                    zorder=1,
                )
        self.ax_cloud.set_title(
            "Atom-Cloud Size Evolution Over 0 to T",
            color=INK,
            fontsize=13,
            fontfamily=PLOT_TITLE_FONT,
        )
        self.ax_cloud.set_xlabel(
            f"Free-expansion time T ({self.cloud_time_unit_for_plot})"
        )
        self.ax_cloud.set_ylabel("Cloud sigma_r (mm)")
        self.ax_cloud.grid(True, color="#e3ded7", linewidth=0.8)
        self.ax_cloud.xaxis.set_major_locator(MaxNLocator(nbins=6))
        self.ax_cloud.yaxis.set_major_locator(MaxNLocator(nbins=6))
        self._set_cloud_axis_limits(display_runs)
        if show_legend:
            self.ax_cloud.legend(
                loc="best",
                fontsize=8,
                frameon=True,
                facecolor="#ffffff",
                edgecolor="#d0dce8",
            )

        for axis in (self.ax_rabi, self.ax_cloud):
            axis.set_facecolor("#fcfdff")
            for spine in axis.spines.values():
                spine.set_color("#cbd6e0")

        self._initialize_plot_interaction_artists()
        self._record_default_plot_limits()
        self.plot_hover_var.set(
            "Move the cursor over a curve to inspect the nearest sample."
        )
        self.plot_marker_var.set(
            "Click inside a plot to pin a marker. Double-click to reset the view."
        )
        self.canvas.draw_idle()

    def _update_derived_text(
        self, params: RamanSimulationParameters, result: RamanSimulationResult
    ) -> None:
        summary = (
            "Current simulation summary\n"
            "\n"
            f"Locked reference curves: {len(self.locked_results)}\n"
            f"Transverse temperature: {params.transverse_temperature_uK:,.6f} uK\n"
            f"Separate longitudinal temperature enabled: {params.use_separate_longitudinal_temperature}\n"
            f"Longitudinal temperature: {params.longitudinal_temperature_uK:,.6f} uK\n"
            f"Transverse velocity sigma: {result.transverse_sigma_mm_s:,.4f} mm/s\n"
            f"Longitudinal velocity sigma: {result.longitudinal_sigma_mm_s:,.4f} mm/s\n"
            f"Initial cloud sigma_r(0): {params.initial_cloud_sigma_mm:,.4f} mm\n"
            f"Cloud sigma_r(T) at the Raman interaction time: {result.expansion_cloud_sigma_mm:,.4f} mm\n"
            f"Expansion time used in P(T, tau): {params.expansion_time_ms:,.4f} ms\n"
            "\n"
            f"On-axis P1 peak intensity: {result.p1_peak_intensity_w_m2:,.4f} W/m^2\n"
            f"On-axis P2 peak intensity: {result.p2_peak_intensity_w_m2:,.4f} W/m^2\n"
            f"On-axis effective Raman Rabi frequency Omega_eff(0) / 2pi: {result.on_axis_rabi_khz:,.4f} kHz\n"
            f"Estimated on-axis pi-pulse time: {result.pi_pulse_time_us:,.4f} us\n"
            "\n"
            f"Large detuning desacc / 2pi: {params.desacc_mhz:,.4f} MHz\n"
            f"Two-photon detuning d / 2pi: {params.two_photon_detuning_khz:,.4f} kHz\n"
            f"Attenuation factor: {params.attenuation:,.4f}\n"
            f"Coupling gain G: {params.gain:,.4f}\n"
            "\n"
            f"Numerical grid: {params.radial_points} radial points x {params.velocity_points} velocity points\n"
            f"Integration cutoffs: {params.radial_cutoff_waists:,.3f} x w0 and {params.velocity_cutoff_sigma:,.3f} x sigma_v,L\n"
            "\n"
            "Interpretation note\n"
            "\n"
            "The lower panel reports the free-expansion cloud size over 0 to the selected interaction time T. "
            "The transverse temperature controls this expansion and the radial beam convolution, while the longitudinal "
            "temperature controls the velocity-selection distribution used in P(T, tau)."
        )

        self.derived_text.configure(state="normal")
        self.derived_text.delete("1.0", "end")
        self.derived_text.insert("1.0", summary)
        self.derived_text.configure(state="disabled")


def main() -> None:
    root = tk.Tk()
    RamanCalculatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
