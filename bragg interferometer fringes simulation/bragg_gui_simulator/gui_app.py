#!/usr/bin/env python3
from __future__ import annotations

import argparse
import queue
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from simulator_core import (
    BraggSimulationConfig,
    config_to_dict,
    default_config,
    format_result_summary,
    legacy_asd_amplitude_to_psd_db,
    load_config,
    plot_results_on_axes,
    save_all_outputs,
    save_config,
    simulate_fringe,
    update_output_prefix,
)


@dataclass(frozen=True)
class ParameterSpec:
    key: str
    label: str
    caster: Callable[[str], Any]
    unit: str
    help_text: str


def int_from_text(value: str) -> int:
    return int(float(value))


def float_from_text(value: str) -> float:
    return float(value)


def strip_output_extensions(path_text: str) -> str:
    path = Path(path_text)
    text = str(path)
    for suffix in (".summary.json", ".json", ".csv", ".png"):
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def get_nested(data: dict[str, Any], key: str) -> Any:
    current: Any = data
    for part in key.split("."):
        current = current[part]
    return current


def set_nested(data: dict[str, Any], key: str, value: Any) -> None:
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


HELP_TEXTS: dict[str, str] = {
    "interferometer.bragg_order": (
        "Bragg order n.\n\n"
        "This model uses the effective wavevector k_eff = 2 n (2 pi / lambda).\n"
        "The scanned optical phase enters as n * phi0, and the inertial phase uses\n"
        "Delta phi_inertial = k_eff * a_eff * T^2."
    ),
    "interferometer.wavelength_m": (
        "Laser wavelength lambda in metres.\n\n"
        "It sets the single-photon wavevector k = 2 pi / lambda and therefore the\n"
        "effective Bragg wavevector k_eff = 2 n k."
    ),
    "interferometer.pulse_separation_s": (
        "Pulse separation T in seconds for the pi/2 - pi - pi/2 sequence.\n\n"
        "For the effective Mach-Zehnder model, the inertial phase scales as\n"
        "Delta phi_inertial = k_eff * a_eff * T^2.\n"
        "The transfer function H(f) also depends strongly on T."
    ),
    "interferometer.effective_acceleration_mps2": (
        "Effective acceleration a_eff in m/s^2.\n\n"
        "This can represent gravity projection, platform acceleration, or another\n"
        "constant acceleration projected along k_eff.\n"
        "The model uses Delta phi_inertial = k_eff * a_eff * T^2."
    ),
    "interferometer.additional_phase_offset_rad": (
        "Additional static phase offset in radians.\n\n"
        "Use this to represent a fixed bias phase that is not already included in the\n"
        "acceleration term or in the pulse diffraction phases."
    ),
    "pulse.transfer_probability": (
        "Effective population-transfer probability P for one Bragg pulse.\n\n"
        "The GUI asks for P directly. If you start from an effective two-state Rabi\n"
        "model, a common estimate is\n"
        "P = (Omega_eff^2 / (Omega_eff^2 + Delta^2)) * sin^2(0.5 * tau * sqrt(Omega_eff^2 + Delta^2)).\n"
        "This program does not force the pi/2 pulse efficiency to be half of the pi pulse."
    ),
    "pulse.loss_probability": (
        "Effective loss probability L for one pulse.\n\n"
        "Population that leaks into parasitic momentum ports is removed from the modeled\n"
        "two-port interferometer. The pulse matrix is scaled by sqrt(1 - L)."
    ),
    "pulse.diffraction_phase_rad": (
        "Effective diffraction phase phi_d in radians.\n\n"
        "This term is applied to the off-diagonal pulse coupling and shifts the final\n"
        "interferometer phase. It is a compact way to include phase shifts caused by\n"
        "non-ideal Bragg diffraction."
    ),
    "pulse.transfer_jitter_std": (
        "Shot-to-shot standard deviation of the transfer probability.\n\n"
        "Each shot samples P' from a Gaussian distribution around the nominal value and\n"
        "clips the result into [0, 1]. This is useful for pulse-area fluctuations."
    ),
    "pulse.phase_jitter_std_rad": (
        "Shot-to-shot standard deviation of the pulse diffraction phase in radians.\n\n"
        "Each shot samples phi_d' from a Gaussian distribution around the nominal phase."
    ),
    "noise.f_min_hz": (
        "Lower integration limit for the noise transfer-function calculation in Hz.\n\n"
        "The program integrates |H(f)|^2 S_phi(f) from f_min to f_max on a log grid."
    ),
    "noise.f_max_hz": (
        "Upper integration limit for the noise transfer-function calculation in Hz.\n\n"
        "Choose this high enough to include all relevant noise peaks and the useful part\n"
        "of the interferometer transfer function."
    ),
    "noise.num_frequency_points": (
        "Number of frequency points used on the logarithmic integration grid.\n\n"
        "Higher values improve numerical accuracy at the cost of runtime."
    ),
    "noise.laser.white_psd_db": (
        "White laser-frequency-noise PSD level in dB.\n\n"
        "Definition:\n"
        "white_psd_db = 10 log10(S0 / 1 Hz^2/Hz)\n\n"
        "The background laser-frequency-noise PSD is modeled as\n"
        "S_nu(f) = S0 + C1/f + C2/f^2 + sum(peaks).\n"
        "This is converted to interferometer phase PSD through\n"
        "S_phi(f) = n^2 S_nu(f) / f^2."
    ),
    "noise.laser.flicker_psd_1hz_db": (
        "Flicker laser-frequency-noise PSD coefficient in dB, referenced at 1 Hz.\n\n"
        "Definition:\n"
        "flicker_psd_1hz_db = 10 log10(C1 / 1 Hz^2/Hz)\n\n"
        "The corresponding PSD contribution is\n"
        "S_flicker(f) = C1 / f.\n"
        "At f = 1 Hz, the PSD equals C1."
    ),
    "noise.laser.random_walk_psd_1hz_db": (
        "Random-walk laser-frequency-noise PSD coefficient in dB, referenced at 1 Hz.\n\n"
        "Definition:\n"
        "random_walk_psd_1hz_db = 10 log10(C2 / 1 Hz^2/Hz)\n\n"
        "The corresponding PSD contribution is\n"
        "S_rw(f) = C2 / f^2.\n"
        "At f = 1 Hz, the PSD equals C2."
    ),
    "noise.mirror.white_psd_db": (
        "White mirror-acceleration PSD level in dB.\n\n"
        "Definition:\n"
        "white_psd_db = 10 log10(S0 / 1 (m/s^2)^2/Hz)\n\n"
        "The background acceleration PSD is modeled as\n"
        "S_a(f) = S0 + C1/f + C2/f^2 + sum(peaks).\n"
        "This is converted to interferometer phase PSD through\n"
        "S_phi(f) = k_eff^2 S_a(f) / (2 pi f)^4."
    ),
    "noise.mirror.flicker_psd_1hz_db": (
        "Flicker mirror-acceleration PSD coefficient in dB, referenced at 1 Hz.\n\n"
        "Definition:\n"
        "flicker_psd_1hz_db = 10 log10(C1 / 1 (m/s^2)^2/Hz)\n\n"
        "The corresponding PSD contribution is\n"
        "S_flicker(f) = C1 / f.\n"
        "At f = 1 Hz, the PSD equals C1."
    ),
    "noise.mirror.random_walk_psd_1hz_db": (
        "Random-walk mirror-acceleration PSD coefficient in dB, referenced at 1 Hz.\n\n"
        "Definition:\n"
        "random_walk_psd_1hz_db = 10 log10(C2 / 1 (m/s^2)^2/Hz)\n\n"
        "The corresponding PSD contribution is\n"
        "S_rw(f) = C2 / f^2.\n"
        "At f = 1 Hz, the PSD equals C2."
    ),
    "noise.peaks.center_hz": (
        "Centre frequency of a Lorentzian noise peak in Hz.\n\n"
        "Use this for narrow resonances such as acoustic or platform modes."
    ),
    "noise.peaks.width_hz": (
        "Half-width parameter of a Lorentzian noise peak in Hz.\n\n"
        "The Lorentzian PSD contribution is\n"
        "S_peak(f) = S_peak_center / (1 + ((f - f0)/width)^2)."
    ),
    "noise.peaks.psd_db": (
        "Peak Lorentzian PSD level in dB.\n\n"
        "The entered value is interpreted as\n"
        "PSD_dB = 10 * log10(S_peak / S_ref),\n"
        "where S_ref = 1 Hz^2/Hz for laser-frequency noise and\n"
        "S_ref = 1 (m/s^2)^2/Hz for mirror-acceleration noise.\n\n"
        "The Lorentzian contribution is\n"
        "S_peak(f) = S_peak_center / (1 + ((f - f0)/width)^2).\n"
        "If you start from an ASD peak amplitude A, then\n"
        "PSD_dB = 10 log10(A^2) = 20 log10(A)\n"
        "relative to the corresponding base-unit reference."
    ),
    "simulation.shots_per_phase": (
        "Number of Monte Carlo shots simulated at each scanned phase value.\n\n"
        "Larger values reduce the estimator noise in the plotted fringe."
    ),
    "simulation.n_phase_points": (
        "Number of scanned phase values between the start and stop of the phase scan.\n\n"
        "This controls the horizontal sampling density of the fringe."
    ),
    "simulation.scan_start_rad": (
        "Start of the scanned optical phase phi0 in radians.\n\n"
        "The final fringe oscillates as cos(n * phi0 + phase_offset)."
    ),
    "simulation.scan_stop_rad": (
        "End of the scanned optical phase phi0 in radians.\n\n"
        "A full 0 to 2 pi scan is typical when plotting one full optical-phase period."
    ),
    "simulation.random_seed": (
        "Random seed for the Monte Carlo simulation.\n\n"
        "Keep this fixed for reproducible comparisons between parameter sets."
    ),
    "simulation.output_prefix": (
        "Output-file prefix used when exporting results.\n\n"
        "The program appends .csv, .summary.json, and .png to this prefix."
    ),
}


INTERFEROMETER_SPECS = [
    ParameterSpec(
        "interferometer.bragg_order",
        "Bragg order",
        int_from_text,
        "",
        HELP_TEXTS["interferometer.bragg_order"],
    ),
    ParameterSpec(
        "interferometer.wavelength_m",
        "Wavelength",
        float_from_text,
        "m",
        HELP_TEXTS["interferometer.wavelength_m"],
    ),
    ParameterSpec(
        "interferometer.pulse_separation_s",
        "Pulse separation T",
        float_from_text,
        "s",
        HELP_TEXTS["interferometer.pulse_separation_s"],
    ),
    ParameterSpec(
        "interferometer.effective_acceleration_mps2",
        "Effective acceleration",
        float_from_text,
        "m/s^2",
        HELP_TEXTS["interferometer.effective_acceleration_mps2"],
    ),
    ParameterSpec(
        "interferometer.additional_phase_offset_rad",
        "Additional phase offset",
        float_from_text,
        "rad",
        HELP_TEXTS["interferometer.additional_phase_offset_rad"],
    ),
]


def pulse_specs(prefix: str) -> list[ParameterSpec]:
    return [
        ParameterSpec(
            f"{prefix}.transfer_probability",
            "Transfer probability",
            float_from_text,
            "",
            HELP_TEXTS["pulse.transfer_probability"],
        ),
        ParameterSpec(
            f"{prefix}.loss_probability",
            "Loss probability",
            float_from_text,
            "",
            HELP_TEXTS["pulse.loss_probability"],
        ),
        ParameterSpec(
            f"{prefix}.diffraction_phase_rad",
            "Diffraction phase",
            float_from_text,
            "rad",
            HELP_TEXTS["pulse.diffraction_phase_rad"],
        ),
        ParameterSpec(
            f"{prefix}.transfer_jitter_std",
            "Transfer jitter sigma",
            float_from_text,
            "",
            HELP_TEXTS["pulse.transfer_jitter_std"],
        ),
        ParameterSpec(
            f"{prefix}.phase_jitter_std_rad",
            "Phase jitter sigma",
            float_from_text,
            "rad",
            HELP_TEXTS["pulse.phase_jitter_std_rad"],
        ),
    ]


NOISE_GRID_SPECS = [
    ParameterSpec("noise.f_min_hz", "Integration f_min", float_from_text, "Hz", HELP_TEXTS["noise.f_min_hz"]),
    ParameterSpec("noise.f_max_hz", "Integration f_max", float_from_text, "Hz", HELP_TEXTS["noise.f_max_hz"]),
    ParameterSpec(
        "noise.num_frequency_points",
        "Frequency grid points",
        int_from_text,
        "",
        HELP_TEXTS["noise.num_frequency_points"],
    ),
]


LASER_NOISE_SPECS = [
    ParameterSpec(
        "noise.laser_frequency_noise_hz_per_sqrt_hz.white_psd_db",
        "White PSD level",
        float_from_text,
        "dB re 1 Hz^2/Hz",
        HELP_TEXTS["noise.laser.white_psd_db"],
    ),
    ParameterSpec(
        "noise.laser_frequency_noise_hz_per_sqrt_hz.flicker_psd_1hz_db",
        "Flicker PSD @ 1 Hz",
        float_from_text,
        "dB re 1 Hz^2/Hz",
        HELP_TEXTS["noise.laser.flicker_psd_1hz_db"],
    ),
    ParameterSpec(
        "noise.laser_frequency_noise_hz_per_sqrt_hz.random_walk_psd_1hz_db",
        "Random-walk PSD @ 1 Hz",
        float_from_text,
        "dB re 1 Hz^2/Hz",
        HELP_TEXTS["noise.laser.random_walk_psd_1hz_db"],
    ),
]


MIRROR_NOISE_SPECS = [
    ParameterSpec(
        "noise.mirror_acceleration_noise_mps2_per_sqrt_hz.white_psd_db",
        "White PSD level",
        float_from_text,
        "dB re 1 (m/s^2)^2/Hz",
        HELP_TEXTS["noise.mirror.white_psd_db"],
    ),
    ParameterSpec(
        "noise.mirror_acceleration_noise_mps2_per_sqrt_hz.flicker_psd_1hz_db",
        "Flicker PSD @ 1 Hz",
        float_from_text,
        "dB re 1 (m/s^2)^2/Hz",
        HELP_TEXTS["noise.mirror.flicker_psd_1hz_db"],
    ),
    ParameterSpec(
        "noise.mirror_acceleration_noise_mps2_per_sqrt_hz.random_walk_psd_1hz_db",
        "Random-walk PSD @ 1 Hz",
        float_from_text,
        "dB re 1 (m/s^2)^2/Hz",
        HELP_TEXTS["noise.mirror.random_walk_psd_1hz_db"],
    ),
]


SIMULATION_SPECS = [
    ParameterSpec(
        "simulation.shots_per_phase",
        "Shots per phase",
        int_from_text,
        "",
        HELP_TEXTS["simulation.shots_per_phase"],
    ),
    ParameterSpec(
        "simulation.n_phase_points",
        "Phase points",
        int_from_text,
        "",
        HELP_TEXTS["simulation.n_phase_points"],
    ),
    ParameterSpec(
        "simulation.scan_start_rad",
        "Scan start",
        float_from_text,
        "rad",
        HELP_TEXTS["simulation.scan_start_rad"],
    ),
    ParameterSpec(
        "simulation.scan_stop_rad",
        "Scan stop",
        float_from_text,
        "rad",
        HELP_TEXTS["simulation.scan_stop_rad"],
    ),
    ParameterSpec(
        "simulation.random_seed",
        "Random seed",
        int_from_text,
        "",
        HELP_TEXTS["simulation.random_seed"],
    ),
    ParameterSpec(
        "simulation.output_prefix",
        "Output prefix",
        str,
        "",
        HELP_TEXTS["simulation.output_prefix"],
    ),
]


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas)

        self.inner.bind(
            "<Configure>",
            lambda event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        window_id = canvas.create_window((0, 0), window=self.inner, anchor="nw")

        def resize_inner(event: tk.Event[tk.Misc]) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        canvas.bind("<Configure>", resize_inner)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = canvas


class PeakTable(ttk.LabelFrame):
    def __init__(self, parent: tk.Misc, title: str, psd_reference_label: str) -> None:
        super().__init__(parent, text=title, padding=10)
        self.psd_reference_label = psd_reference_label
        self.rows: list[dict[str, Any]] = []
        self.table = ttk.Frame(self)
        self.table.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self._build_header()
        ttk.Button(self, text="Add peak", command=self.add_empty_row).grid(row=1, column=0, sticky="w", pady=(8, 0))

    def _build_header(self) -> None:
        headers = [
            ("Center [Hz]", HELP_TEXTS["noise.peaks.center_hz"]),
            ("Width [Hz]", HELP_TEXTS["noise.peaks.width_hz"]),
            (f"Peak PSD [dB re {self.psd_reference_label}]", HELP_TEXTS["noise.peaks.psd_db"]),
        ]
        for index, (label, help_text) in enumerate(headers):
            ttk.Label(self.table, text=label).grid(row=0, column=index * 2, sticky="w", padx=(0, 6))
            ttk.Button(
                self.table,
                text="?",
                width=2,
                command=lambda text=help_text, title=label: messagebox.showinfo(title, text, parent=self.winfo_toplevel()),
            ).grid(row=0, column=index * 2 + 1, sticky="w", padx=(0, 12))
        ttk.Label(self.table, text="Action").grid(row=0, column=6, sticky="w")

    def clear_rows(self) -> None:
        for row in self.rows:
            for widget in row["widgets"]:
                widget.destroy()
        self.rows.clear()

    def add_row(self, center_hz: Any = "", width_hz: Any = "", psd_db: Any = "") -> None:
        row_index = len(self.rows) + 1
        center_var = tk.StringVar(value=str(center_hz))
        width_var = tk.StringVar(value=str(width_hz))
        psd_db_var = tk.StringVar(value=str(psd_db))
        entries: list[tk.Widget] = []
        for column, variable in enumerate((center_var, width_var, psd_db_var)):
            entry = ttk.Entry(self.table, textvariable=variable, width=12)
            entry.grid(row=row_index, column=column * 2, columnspan=2, sticky="ew", padx=(0, 12), pady=3)
            entries.append(entry)
        remove_button = ttk.Button(
            self.table,
            text="Remove",
            command=lambda index=row_index - 1: self.remove_row(index),
        )
        remove_button.grid(row=row_index, column=6, sticky="w", pady=3)
        entries.append(remove_button)
        self.rows.append(
            {
                "center_var": center_var,
                "width_var": width_var,
                "psd_db_var": psd_db_var,
                "widgets": entries,
            }
        )

    def add_empty_row(self) -> None:
        self.add_row("", "", "")

    def remove_row(self, index: int) -> None:
        if not (0 <= index < len(self.rows)):
            return
        for widget in self.rows[index]["widgets"]:
            widget.destroy()
        del self.rows[index]
        existing = self.get_data()
        self.clear_rows()
        for item in existing:
            self.add_row(item["center_hz"], item["width_hz"], item["psd_db"])

    def load_data(self, peaks: list[dict[str, Any]]) -> None:
        self.clear_rows()
        for peak in peaks:
            if "psd_db" in peak:
                psd_db = peak["psd_db"]
            else:
                amplitude = peak.get("amplitude", "")
                psd_db = legacy_asd_amplitude_to_psd_db(float(amplitude)) if amplitude != "" else ""
            self.add_row(peak["center_hz"], peak["width_hz"], psd_db)

    def get_data(self) -> list[dict[str, float]]:
        peaks: list[dict[str, float]] = []
        for index, row in enumerate(self.rows, start=1):
            center_text = row["center_var"].get().strip()
            width_text = row["width_var"].get().strip()
            psd_db_text = row["psd_db_var"].get().strip()
            if not center_text and not width_text and not psd_db_text:
                continue
            try:
                center_hz = float(center_text)
                width_hz = float(width_text)
                psd_db = float(psd_db_text)
            except ValueError as exc:
                raise ValueError(f"Invalid peak row {index} in {self['text']}.") from exc
            peaks.append(
                {
                    "center_hz": center_hz,
                    "width_hz": width_hz,
                    "psd_db": psd_db,
                }
            )
        return peaks


class SimulationApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Bragg Atom Interferometer Simulator")
        self.geometry("1500x920")
        self.minsize(1200, 760)
        self.current_config_path: Path | None = None
        self.current_results: dict[str, Any] | None = None
        self.current_run_config: BraggSimulationConfig | None = None
        self.run_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.is_running = False
        self.parameter_vars: dict[str, tuple[tk.StringVar, ParameterSpec]] = {}
        self.has_plot_backend = False

        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_controls()
        self._build_main_panes()
        self._build_plot_panel()
        self.populate_form(default_config())

    def _build_controls(self) -> None:
        controls = ttk.Frame(self, padding=(12, 10))
        controls.grid(row=0, column=0, sticky="ew")
        for column in range(9):
            controls.columnconfigure(column, weight=0)
        controls.columnconfigure(7, weight=1)

        self.load_button = ttk.Button(controls, text="Load Config...", command=self.load_config_dialog)
        self.load_button.grid(row=0, column=0, padx=(0, 8))
        self.save_button = ttk.Button(controls, text="Export Config...", command=self.export_config_dialog)
        self.save_button.grid(row=0, column=1, padx=(0, 8))
        self.default_button = ttk.Button(controls, text="Restore Defaults", command=self.restore_defaults)
        self.default_button.grid(row=0, column=2, padx=(0, 8))
        self.run_button = ttk.Button(controls, text="Run Simulation", command=self.run_simulation)
        self.run_button.grid(row=0, column=3, padx=(0, 8))
        self.export_results_button = ttk.Button(controls, text="Export Results...", command=self.export_results_dialog)
        self.export_results_button.grid(row=0, column=4, padx=(0, 8))
        self.scope_button = ttk.Button(controls, text="Model Scope", command=self.show_model_scope)
        self.scope_button.grid(row=0, column=5, padx=(0, 8))

        self.status_var = tk.StringVar(
            value="Ready. Edit parameters, load a JSON config, or run the default example."
        )
        ttk.Label(controls, textvariable=self.status_var, anchor="w").grid(row=0, column=7, sticky="ew", padx=(12, 0))

    def _build_main_panes(self) -> None:
        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        editor_panel = ttk.Frame(paned, padding=(0, 0, 8, 0))
        editor_panel.columnconfigure(0, weight=1)
        editor_panel.rowconfigure(0, weight=1)
        paned.add(editor_panel, weight=5)

        result_panel = ttk.Frame(paned)
        result_panel.columnconfigure(0, weight=1)
        result_panel.rowconfigure(1, weight=1)
        paned.add(result_panel, weight=6)

        self.notebook = ttk.Notebook(editor_panel)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self._build_parameter_tabs()
        self._build_result_panel(result_panel)

    def _build_parameter_tabs(self) -> None:
        self.interferometer_tab = ScrollableFrame(self.notebook)
        self.pulses_tab = ScrollableFrame(self.notebook)
        self.noise_tab = ScrollableFrame(self.notebook)
        self.simulation_tab = ScrollableFrame(self.notebook)

        self.notebook.add(self.interferometer_tab, text="Interferometer")
        self.notebook.add(self.pulses_tab, text="Pulses")
        self.notebook.add(self.noise_tab, text="Noise")
        self.notebook.add(self.simulation_tab, text="Simulation")

        self._build_spec_group(
            self.interferometer_tab.inner,
            "Interferometer Parameters",
            INTERFEROMETER_SPECS,
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        self.interferometer_tab.inner.columnconfigure(0, weight=1)

        pulse_parent = self.pulses_tab.inner
        self._build_spec_group(pulse_parent, "First Beam Splitter (pi/2)", pulse_specs("beam_splitter_1")).grid(
            row=0, column=0, sticky="ew", padx=12, pady=(12, 6)
        )
        self._build_spec_group(pulse_parent, "Mirror Pulse (pi)", pulse_specs("mirror")).grid(
            row=1, column=0, sticky="ew", padx=12, pady=6
        )
        self._build_spec_group(pulse_parent, "Second Beam Splitter (pi/2)", pulse_specs("beam_splitter_2")).grid(
            row=2, column=0, sticky="ew", padx=12, pady=6
        )
        pulse_parent.columnconfigure(0, weight=1)

        noise_parent = self.noise_tab.inner
        self._build_spec_group(noise_parent, "Frequency Grid", NOISE_GRID_SPECS).grid(
            row=0, column=0, sticky="ew", padx=12, pady=(12, 6)
        )
        self._build_spec_group(noise_parent, "Laser Frequency Noise", LASER_NOISE_SPECS).grid(
            row=1, column=0, sticky="ew", padx=12, pady=6
        )
        self.laser_peak_table = PeakTable(noise_parent, "Laser Lorentzian Peaks", "1 Hz^2/Hz")
        self.laser_peak_table.grid(row=2, column=0, sticky="ew", padx=12, pady=6)

        self._build_spec_group(noise_parent, "Mirror Acceleration Noise", MIRROR_NOISE_SPECS).grid(
            row=3, column=0, sticky="ew", padx=12, pady=6
        )
        self.mirror_peak_table = PeakTable(noise_parent, "Mirror Lorentzian Peaks", "1 (m/s^2)^2/Hz")
        self.mirror_peak_table.grid(row=4, column=0, sticky="ew", padx=12, pady=(6, 12))
        noise_parent.columnconfigure(0, weight=1)

        simulation_group = self._build_spec_group(
            self.simulation_tab.inner,
            "Simulation Controls",
            SIMULATION_SPECS,
        )
        simulation_group.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        self._add_output_prefix_button(simulation_group)
        self.simulation_tab.inner.columnconfigure(0, weight=1)

    def _build_spec_group(
        self,
        parent: tk.Misc,
        title: str,
        specs: list[ParameterSpec],
    ) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text=title, padding=12)
        frame.columnconfigure(1, weight=1)
        for row, spec in enumerate(specs):
            ttk.Label(frame, text=spec.label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
            variable = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=variable, width=22)
            entry.grid(row=row, column=1, sticky="ew", padx=(0, 8), pady=4)
            if spec.unit:
                ttk.Label(frame, text=spec.unit).grid(row=row, column=2, sticky="w", padx=(0, 8), pady=4)
            else:
                ttk.Label(frame, text="").grid(row=row, column=2, sticky="w", padx=(0, 8), pady=4)
            ttk.Button(
                frame,
                text="?",
                width=2,
                command=lambda text=spec.help_text, title=spec.label: self.show_help(title, text),
            ).grid(row=row, column=3, sticky="w", pady=4)
            self.parameter_vars[spec.key] = (variable, spec)
        return frame

    def _add_output_prefix_button(self, parent: ttk.LabelFrame) -> None:
        button = ttk.Button(parent, text="Choose...", command=self.choose_output_prefix)
        button.grid(row=len(SIMULATION_SPECS) - 1, column=4, sticky="w", padx=(6, 0), pady=4)

    def _build_result_panel(self, parent: ttk.Frame) -> None:
        summary_frame = ttk.LabelFrame(parent, text="Run Summary", padding=12)
        summary_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        summary_frame.columnconfigure(0, weight=1)

        self.summary_text = tk.Text(summary_frame, height=9, wrap="word", state="disabled")
        self.summary_text.grid(row=0, column=0, sticky="ew")

        result_notes = (
            "The GUI keeps an effective two-port Bragg model. Use the parameter help buttons "
            "for definitions, units, and formulas."
        )
        ttk.Label(parent, text=result_notes, wraplength=720, justify="left").grid(
            row=2, column=0, sticky="ew", pady=(8, 0)
        )

        self.plot_host = ttk.Frame(parent)
        self.plot_host.grid(row=1, column=0, sticky="nsew")
        self.plot_host.columnconfigure(0, weight=1)
        self.plot_host.rowconfigure(0, weight=1)

    def _build_plot_panel(self) -> None:
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
            from matplotlib.figure import Figure
        except ImportError:
            ttk.Label(
                self.plot_host,
                text=(
                    "matplotlib is not available in this Python environment.\n"
                    "The simulator can still run, but live plots are disabled."
                ),
                justify="center",
            ).grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
            self.fringe_axis = None
            self.noise_axis = None
            self.canvas = None
            return

        figure = Figure(figsize=(8.0, 7.2), dpi=100)
        self.fringe_axis = figure.add_subplot(211)
        self.noise_axis = figure.add_subplot(212)
        figure.tight_layout()
        self.figure = figure
        self.has_plot_backend = True

        self.canvas = FigureCanvasTkAgg(figure, master=self.plot_host)
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.grid(row=0, column=0, sticky="nsew")
        toolbar = NavigationToolbar2Tk(self.canvas, self.plot_host, pack_toolbar=False)
        toolbar.update()
        toolbar.grid(row=1, column=0, sticky="ew")
        self.canvas.draw_idle()

    def show_help(self, title: str, help_text: str) -> None:
        messagebox.showinfo(title, help_text, parent=self)

    def show_model_scope(self) -> None:
        message = (
            "Model scope:\n\n"
            "1. The simulator uses an effective two-path Bragg Mach-Zehnder model.\n"
            "2. Each Bragg pulse is represented by a 2x2 complex matrix with independent\n"
            "   transfer probability, loss, diffraction phase, and shot-to-shot jitter.\n"
            "3. Laser-frequency noise and mirror vibration noise are converted into phase\n"
            "   noise with the interferometer transfer function and then sampled shot by shot.\n"
            "4. This is appropriate for fringe prediction and noise budgeting, but it is not\n"
            "   a full momentum-lattice propagation code."
        )
        messagebox.showinfo("Model Scope", message, parent=self)

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def set_summary_text(self, text: str) -> None:
        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", text)
        self.summary_text.configure(state="disabled")

    def populate_form(self, cfg: BraggSimulationConfig) -> None:
        data = config_to_dict(cfg)
        for key, (variable, spec) in self.parameter_vars.items():
            value = get_nested(data, key)
            if spec.caster is str:
                variable.set(str(value))
            else:
                variable.set(f"{value}")
        self.laser_peak_table.load_data(data["noise"]["laser_frequency_noise_hz_per_sqrt_hz"]["peaks"])
        self.mirror_peak_table.load_data(data["noise"]["mirror_acceleration_noise_mps2_per_sqrt_hz"]["peaks"])
        self.current_results = None
        self.current_run_config = None
        self.set_summary_text("No simulation run yet.")
        if self.has_plot_backend and self.fringe_axis is not None and self.noise_axis is not None and self.canvas is not None:
            self.fringe_axis.clear()
            self.noise_axis.clear()
            self.fringe_axis.set_title("Run a simulation to display the fringe.")
            self.noise_axis.set_title("Run a simulation to display the noise weighting.")
            self.canvas.draw_idle()

    def read_config_from_form(self) -> BraggSimulationConfig:
        data = config_to_dict(default_config())
        for key, (variable, spec) in self.parameter_vars.items():
            text = variable.get().strip()
            if not text:
                raise ValueError(f"Parameter '{spec.label}' is empty.")
            try:
                value = spec.caster(text)
            except ValueError as exc:
                raise ValueError(f"Invalid value for '{spec.label}': {text}") from exc
            if key == "simulation.output_prefix":
                value = strip_output_extensions(str(value))
            set_nested(data, key, value)

        data["noise"]["laser_frequency_noise_hz_per_sqrt_hz"]["peaks"] = self.laser_peak_table.get_data()
        data["noise"]["mirror_acceleration_noise_mps2_per_sqrt_hz"]["peaks"] = self.mirror_peak_table.get_data()
        return BraggSimulationConfig.from_dict(data)

    def load_config_dialog(self) -> None:
        path_text = filedialog.askopenfilename(
            parent=self,
            title="Load configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path_text:
            return
        try:
            cfg = load_config(path_text)
        except Exception as exc:
            messagebox.showerror("Load failed", f"Could not load configuration:\n{exc}", parent=self)
            return
        self.current_config_path = Path(path_text)
        self.populate_form(cfg)
        self.set_status(f"Loaded configuration from {self.current_config_path}")

    def export_config_dialog(self) -> None:
        try:
            cfg = self.read_config_from_form()
        except Exception as exc:
            messagebox.showerror("Invalid configuration", str(exc), parent=self)
            return

        initial_path = self.current_config_path or Path("bragg_gui_simulator") / "config_export.json"
        path_text = filedialog.asksaveasfilename(
            parent=self,
            title="Export configuration",
            defaultextension=".json",
            initialfile=initial_path.name,
            initialdir=str(initial_path.parent),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path_text:
            return
        saved_path = save_config(cfg, path_text)
        self.current_config_path = saved_path
        self.set_status(f"Exported configuration to {saved_path}")

    def restore_defaults(self) -> None:
        self.current_config_path = None
        self.populate_form(default_config())
        self.set_status("Restored the built-in default configuration.")

    def choose_output_prefix(self) -> None:
        current_var, _ = self.parameter_vars["simulation.output_prefix"]
        initial = strip_output_extensions(current_var.get().strip() or "outputs/bragg_gui_run")
        chosen = filedialog.asksaveasfilename(
            parent=self,
            title="Choose output prefix",
            initialfile=Path(initial).name,
            initialdir=str(Path(initial).parent),
            filetypes=[("All files", "*.*")],
        )
        if chosen:
            current_var.set(strip_output_extensions(chosen))

    def set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in (
            self.load_button,
            self.save_button,
            self.default_button,
            self.run_button,
            self.export_results_button,
            self.scope_button,
        ):
            button.configure(state=state)

    def run_simulation(self) -> None:
        if self.is_running:
            return
        try:
            cfg = self.read_config_from_form()
        except Exception as exc:
            messagebox.showerror("Invalid configuration", str(exc), parent=self)
            return

        self.is_running = True
        self.set_controls_enabled(False)
        self.set_status("Running simulation...")
        self.set_summary_text("Simulation is running. Results will appear here when the calculation finishes.")

        worker = threading.Thread(target=self._worker_run_simulation, args=(cfg,), daemon=True)
        worker.start()
        self.after(120, self.poll_run_queue)

    def _worker_run_simulation(self, cfg: BraggSimulationConfig) -> None:
        try:
            results = simulate_fringe(cfg)
        except Exception:
            self.run_queue.put(("error", traceback.format_exc()))
            return
        self.run_queue.put(("success", (cfg, results)))

    def poll_run_queue(self) -> None:
        try:
            status, payload = self.run_queue.get_nowait()
        except queue.Empty:
            if self.is_running:
                self.after(120, self.poll_run_queue)
            return

        self.is_running = False
        self.set_controls_enabled(True)

        if status == "error":
            self.set_status("Simulation failed.")
            messagebox.showerror("Simulation failed", payload, parent=self)
            return

        cfg, results = payload
        self.current_run_config = cfg
        self.current_results = results
        self.set_summary_text(format_result_summary(results))
        if self.has_plot_backend and self.fringe_axis is not None and self.noise_axis is not None and self.canvas is not None:
            plot_results_on_axes(cfg, results, (self.fringe_axis, self.noise_axis))
            self.canvas.draw_idle()
        fit = results["fit"]
        self.set_status(
            "Simulation finished. "
            f"Contrast={fit['contrast']:.4f}, phase offset={fit['phase_offset_rad']:.4f} rad."
        )

    def export_results_dialog(self) -> None:
        if self.current_results is None or self.current_run_config is None:
            messagebox.showinfo("No results", "Run a simulation before exporting results.", parent=self)
            return

        current_var, _ = self.parameter_vars["simulation.output_prefix"]
        initial = strip_output_extensions(current_var.get().strip() or "outputs/bragg_gui_run")
        chosen = filedialog.asksaveasfilename(
            parent=self,
            title="Export results",
            initialfile=Path(initial).name,
            initialdir=str(Path(initial).parent),
            filetypes=[("All files", "*.*")],
        )
        if not chosen:
            return

        output_prefix = strip_output_extensions(chosen)
        current_var.set(output_prefix)
        cfg = update_output_prefix(self.current_run_config, output_prefix)
        try:
            output_paths = save_all_outputs(cfg, self.current_results, output_prefix=output_prefix)
        except Exception as exc:
            messagebox.showerror("Export failed", f"Could not export results:\n{exc}", parent=self)
            return

        lines = [f"{key}: {value}" for key, value in output_paths.items() if value is not None]
        if output_paths.get("plot") is None:
            lines.append("plot: matplotlib is not available in this Python environment")
        messagebox.showinfo("Export complete", "\n".join(lines), parent=self)
        self.set_status(f"Exported results to prefix {output_prefix}")


def run_headless(config_path: str | None, output_prefix: str | None) -> int:
    cfg = load_config(config_path)
    if output_prefix:
        cfg = update_output_prefix(cfg, strip_output_extensions(output_prefix))
    results = simulate_fringe(cfg)
    output_paths = save_all_outputs(cfg, results, output_prefix=cfg.simulation.output_prefix)
    print(format_result_summary(results))
    for key, value in output_paths.items():
        print(f"{key}: {value}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GUI front-end for the Bragg atom-interferometer fringe simulator."
    )
    parser.add_argument("--headless-run", action="store_true", help="Run the simulator without launching the GUI.")
    parser.add_argument("--config", type=str, help="JSON configuration file used for headless mode.")
    parser.add_argument("--output-prefix", type=str, help="Override the output prefix in headless mode.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.headless_run:
        return run_headless(args.config, args.output_prefix)

    app = SimulationApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
