from __future__ import annotations

import json
import os
import queue
import threading
import traceback
import webbrowser
from dataclasses import asdict
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import matplotlib
import numpy as np

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

import rb87_bias_coils_current_scan as core


class SimulationThread(threading.Thread):
    def __init__(self, config: core.SimulationConfig, output_queue: queue.Queue):
        super().__init__(daemon=True)
        self.config = config
        self.output_queue = output_queue

    def run(self) -> None:
        try:
            self.output_queue.put(("status", "Running coarse current scan..."))
            output_dir = Path(core.__file__).resolve().parent / self.config.output.directory
            output_dir.mkdir(parents=True, exist_ok=True)

            coarse_result = core.run_scan(self.config)

            self.output_queue.put(("status", "Refining around the coarse optimum..."))
            refinement_result = core.refine_best_current(self.config, coarse_result)
            best_result = coarse_result["best_result"] if refinement_result is None else refinement_result["best_result"]

            self.output_queue.put(("status", "Saving figures and data products..."))
            csv_path = core.save_scan_csv(coarse_result["records"], output_dir, self.config.output.prefix)
            refined_csv_path = None
            if refinement_result is not None and refinement_result["records"]:
                refined_csv_path = core.save_scan_csv(
                    refinement_result["records"],
                    output_dir,
                    f"{self.config.output.prefix}_refined",
                )
            overview_path = core.make_overview_figure(
                self.config,
                coarse_result,
                best_result,
                refinement_result,
                output_dir,
                self.config.output.prefix,
            )
            dynamics_path = core.make_dynamics_figure(
                self.config,
                best_result,
                output_dir,
                self.config.output.prefix,
            )
            summary_path = core.write_summary(
                self.config,
                coarse_result,
                best_result,
                refinement_result,
                output_dir,
                self.config.output.prefix,
            )
            resolved_config_path = core.save_resolved_config(
                self.config,
                output_dir,
                self.config.output.prefix,
            )

            bundle = {
                "config": self.config,
                "coarse_result": coarse_result,
                "refinement_result": refinement_result,
                "best_result": best_result,
                "paths": {
                    "output_dir": output_dir,
                    "csv": csv_path,
                    "refined_csv": refined_csv_path,
                    "overview": overview_path,
                    "dynamics": dynamics_path,
                    "summary": summary_path,
                    "resolved_config": resolved_config_path,
                },
            }
            self.output_queue.put(("result", bundle))
        except Exception:
            self.output_queue.put(("error", traceback.format_exc()))


class InteractivePlotPanel(ttk.Frame):
    def __init__(self, master, title: str, subtitle: str):
        super().__init__(master, style="Panel.TFrame", padding=(14, 12, 14, 14))
        self.export_path: Path | None = None
        self.motion_formatters: dict = {}

        ttk.Label(self, text=title, style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(self, text=subtitle, style="Muted.TLabel", wraplength=920, justify="left").pack(anchor="w", pady=(2, 10))

        toolbar_shell = ttk.Frame(self, style="Panel.TFrame")
        toolbar_shell.pack(fill="x", pady=(0, 6))

        self.figure = Figure(figsize=(10, 8), facecolor="#fbfaf7", constrained_layout=True)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_shell, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side="left", fill="x")

        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.configure(bg="#fbfaf7", highlightthickness=1, highlightbackground="#ddd7cb")
        self.canvas_widget.pack(fill="both", expand=True)

        footer = ttk.Frame(self, style="Panel.TFrame")
        footer.pack(fill="x", pady=(8, 0))
        self.coord_var = tk.StringVar(
            value="Hover over a curve or heatmap to inspect coordinates. Use the toolbar or mouse wheel to zoom."
        )
        ttk.Label(footer, textvariable=self.coord_var, style="Muted.TLabel", wraplength=760, justify="left").pack(
            side="left", fill="x", expand=True
        )
        self.open_button = ttk.Button(footer, text="Open Exported PNG", command=self.open_export, style="Secondary.TButton")
        self.open_button.state(["disabled"])
        self.open_button.pack(side="right")

        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("axes_leave_event", self._on_leave)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.clear("Run a simulation to populate this interactive panel.")

    def clear(self, message: str) -> None:
        self.figure.clear()
        self.figure.text(0.5, 0.5, message, ha="center", va="center", fontsize=13, color="#6a706c")
        self.motion_formatters.clear()
        self.canvas.draw_idle()

    def set_export_path(self, path: Path | None) -> None:
        self.export_path = path
        if path is not None and path.exists():
            self.open_button.state(["!disabled"])
        else:
            self.open_button.state(["disabled"])

    def draw_overview(
        self,
        config: core.SimulationConfig,
        coarse_result: dict,
        best_result: dict,
        refinement_result: dict | None,
    ) -> None:
        self.figure.clear()
        axes = self.figure.subplots(2, 2)
        self.figure.set_constrained_layout(True)
        meta = core.plot_overview_on_axes(config, coarse_result, best_result, refinement_result, axes)
        self.motion_formatters.clear()

        plot_result = meta["plot_result"]
        x_currents = plot_result["x_currents"]
        y_currents = plot_result["y_currents"]
        z_currents = plot_result["z_currents"]
        temp_grid = plot_result["temp_grid"]
        best_iz, best_iy, best_ix = plot_result["best_indices"]

        xy_temp = temp_grid[best_iz, :, :]
        xz_temp = temp_grid[:, best_iy, :]
        yz_temp = temp_grid[:, :, best_ix]

        self.motion_formatters[axes[0, 0]] = self._heatmap_formatter(xy_temp, x_currents, y_currents, "Current X (A)", "Current Y (A)")
        self.motion_formatters[axes[0, 1]] = self._heatmap_formatter(xz_temp, x_currents, z_currents, "Current X (A)", "Current Z (A)")
        self.motion_formatters[axes[1, 0]] = self._heatmap_formatter(yz_temp, y_currents, z_currents, "Current Y (A)", "Current Z (A)")
        self.motion_formatters[axes[1, 1]] = self._line_formatter()
        self.canvas.draw_idle()

    def draw_dynamics(self, config: core.SimulationConfig, best_result: dict) -> None:
        self.figure.clear()
        axes = self.figure.subplots(2, 2)
        self.figure.set_constrained_layout(True)
        core.plot_dynamics_on_axes(config, best_result, axes)
        self.motion_formatters = {ax: self._line_formatter() for ax in axes.flat}
        self.canvas.draw_idle()

    def _heatmap_formatter(self, array, x_values, y_values, x_label: str, y_label: str):
        data = np.asarray(array)
        xs = np.asarray(x_values, dtype=float)
        ys = np.asarray(y_values, dtype=float)

        def formatter(ax, x_value: float, y_value: float) -> str:
            ix = int(np.clip(np.argmin(np.abs(xs - x_value)), 0, len(xs) - 1))
            iy = int(np.clip(np.argmin(np.abs(ys - y_value)), 0, len(ys) - 1))
            z_value = float(data[iy, ix])
            return (
                f"{ax.get_title()} | {x_label} = {xs[ix]:.4f}, "
                f"{y_label} = {ys[iy]:.4f}, value = {z_value:.4f}"
            )

        return formatter

    def _line_formatter(self):
        def formatter(ax, x_value: float, y_value: float) -> str:
            best_line_label = None
            best_line_x = None
            best_line_y = None
            best_distance = float("inf")
            for line in ax.lines:
                x_data = np.asarray(line.get_xdata(), dtype=float)
                y_data = np.asarray(line.get_ydata(), dtype=float)
                if x_data.size == 0 or y_data.size == 0:
                    continue
                index = int(np.argmin(np.abs(x_data - x_value)))
                distance = abs(x_data[index] - x_value)
                if distance < best_distance:
                    best_distance = distance
                    best_line_x = float(x_data[index])
                    best_line_y = float(y_data[index])
                    label = line.get_label()
                    best_line_label = "curve" if not label or label.startswith("_") else label
            if best_line_label is not None:
                x_label = ax.get_xlabel() or "x"
                y_label = ax.get_ylabel() or "y"
                return (
                    f"{ax.get_title()} | {best_line_label}: "
                    f"{x_label} = {best_line_x:.4f}, {y_label} = {best_line_y:.4f}"
                )
            x_label = ax.get_xlabel() or "x"
            y_label = ax.get_ylabel() or "y"
            return f"{ax.get_title()} | {x_label} = {x_value:.4f}, {y_label} = {y_value:.4f}"

        return formatter

    def _on_motion(self, event) -> None:
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            return
        formatter = self.motion_formatters.get(event.inaxes)
        if formatter is None:
            x_label = event.inaxes.get_xlabel() or "x"
            y_label = event.inaxes.get_ylabel() or "y"
            text = f"{event.inaxes.get_title()} | {x_label} = {event.xdata:.4f}, {y_label} = {event.ydata:.4f}"
        else:
            text = formatter(event.inaxes, float(event.xdata), float(event.ydata))
        self.coord_var.set(text)

    def _on_leave(self, event) -> None:
        self.coord_var.set(
            "Hover over a curve or heatmap to inspect coordinates. Use the toolbar or mouse wheel to zoom."
        )

    def _on_scroll(self, event) -> None:
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            return
        ax = event.inaxes
        x_min, x_max = ax.get_xlim()
        y_min, y_max = ax.get_ylim()
        if x_max == x_min or y_max == y_min:
            return

        zoom_in = event.button == "up"
        scale_factor = 1.0 / 1.18 if zoom_in else 1.18

        new_width = (x_max - x_min) * scale_factor
        new_height = (y_max - y_min) * scale_factor
        rel_x = (x_max - event.xdata) / (x_max - x_min)
        rel_y = (y_max - event.ydata) / (y_max - y_min)

        ax.set_xlim([event.xdata - new_width * (1.0 - rel_x), event.xdata + new_width * rel_x])
        ax.set_ylim([event.ydata - new_height * (1.0 - rel_y), event.ydata + new_height * rel_y])
        self.canvas.draw_idle()

    def open_export(self) -> None:
        if self.export_path is not None and self.export_path.exists():
            webbrowser.open(self.export_path.as_uri())


class TkBiasCoilsApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Rb87 Bias-Coil Molasses Simulator")
        self.root.geometry("1560x980")
        self.root.configure(bg="#f4f0e8")

        self.result_queue: queue.Queue = queue.Queue()
        self.worker: SimulationThread | None = None
        self.last_bundle: dict | None = None

        self._configure_style()
        self._build_ui()
        self.apply_config(core.SimulationConfig())
        self.root.after(120, self._poll_queue)

    def _configure_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("App.TFrame", background="#f4f0e8")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("Header.TFrame", background="#123f4d")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("TLabelframe", background="#ffffff", bordercolor="#d9d4ca", borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background="#ffffff", foreground="#154e61", font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background="#ffffff", foreground="#16252d", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#5c665f", font=("Segoe UI", 9))
        style.configure("PanelTitle.TLabel", background="#ffffff", foreground="#10242e", font=("Segoe UI Semibold", 14))
        style.configure("HeaderTitle.TLabel", background="#123f4d", foreground="#ffffff", font=("Georgia", 20, "bold"))
        style.configure("HeaderSub.TLabel", background="#123f4d", foreground="#eaf3f5", font=("Segoe UI", 10))
        style.configure("MetricTitle.TLabel", background="#ffffff", foreground="#6e756f", font=("Segoe UI", 8, "bold"))
        style.configure("MetricValue.TLabel", background="#ffffff", foreground="#13242d", font=("Segoe UI Semibold", 13))
        style.configure("MetricDetail.TLabel", background="#ffffff", foreground="#5b625d", font=("Segoe UI", 9))
        style.configure("Primary.TButton", padding=(12, 9), font=("Segoe UI Semibold", 10))
        style.configure("Secondary.TButton", padding=(12, 9), font=("Segoe UI", 10))
        style.map("Primary.TButton", background=[("active", "#1f6b84"), ("!disabled", "#1b5d73")], foreground=[("!disabled", "#ffffff")])
        style.map("Secondary.TButton", background=[("active", "#f1ece2"), ("!disabled", "#ebe7dd")], foreground=[("!disabled", "#17313c")])
        style.configure("TNotebook", background="#f4f0e8", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 8), font=("Segoe UI", 10))

    def _build_ui(self) -> None:
        root_frame = ttk.Frame(self.root, style="App.TFrame")
        root_frame.pack(fill="both", expand=True, padx=18, pady=18)

        header = ttk.Frame(root_frame, style="Header.TFrame")
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Rb87 Bias-Coil Optical Molasses Simulator", style="HeaderTitle.TLabel").pack(anchor="w", padx=22, pady=(18, 4))
        ttk.Label(
            header,
            text="Interactive current-domain simulation for three-axis compensation coils, with refined overview scans and research-oriented outputs.",
            style="HeaderSub.TLabel",
            wraplength=1200,
            justify="left",
        ).pack(anchor="w", padx=22, pady=(0, 18))

        body = ttk.Panedwindow(root_frame, orient="horizontal")
        body.pack(fill="both", expand=True)

        left_host = ttk.Frame(body, style="App.TFrame")
        right_host = ttk.Frame(body, style="App.TFrame")
        body.add(left_host, weight=1)
        body.add(right_host, weight=3)

        self._build_left_panel(left_host)
        self._build_right_panel(right_host)

        bottom = ttk.Frame(root_frame, style="App.TFrame")
        bottom.pack(fill="x", pady=(10, 0))
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(bottom, textvariable=self.status_var, style="Muted.TLabel").pack(side="left")
        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=220)
        self.progress.pack(side="right")

    def _build_left_panel(self, parent) -> None:
        canvas = tk.Canvas(parent, bg="#f4f0e8", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, style="App.TFrame")
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_session_controls(scroll_frame)
        self._build_reference_box(scroll_frame)
        self.field_vars = self._build_field_group(scroll_frame)
        self.molasses_vars = self._build_molasses_group(scroll_frame)
        self.geometry_vars = self._build_geometry_group(scroll_frame)
        self.scan_vars = self._build_scan_group(scroll_frame)
        self.refinement_vars = self._build_refinement_group(scroll_frame)
        self.output_vars = self._build_output_group(scroll_frame)
        self.derived_labels = self._build_derived_group(scroll_frame)

    def _labelframe(self, parent, text: str) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text=text, padding=(14, 12, 14, 12))
        frame.pack(fill="x", pady=8)
        return frame

    def _build_session_controls(self, parent) -> None:
        frame = self._labelframe(parent, "Session Controls")
        row1 = ttk.Frame(frame, style="Panel.TFrame")
        row1.pack(fill="x")
        self.run_button = ttk.Button(row1, text="Run Simulation", command=self.run_simulation, style="Primary.TButton")
        self.run_button.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(row1, text="Load Config", command=self.load_config_dialog, style="Secondary.TButton").pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row1, text="Save Config", command=self.save_config_dialog, style="Secondary.TButton").pack(side="left", fill="x", expand=True, padx=(6, 0))

        row2 = ttk.Frame(frame, style="Panel.TFrame")
        row2.pack(fill="x", pady=(8, 0))
        ttk.Button(row2, text="Reset Defaults", command=lambda: self.apply_config(core.SimulationConfig()), style="Secondary.TButton").pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(row2, text="Open Output Folder", command=self.open_output_directory, style="Secondary.TButton").pack(side="left", fill="x", expand=True, padx=(6, 0))

        ttk.Label(
            frame,
            text="Keep the coarse scan moderate. The refined overview grid is what preserves the target current resolution.",
            style="Muted.TLabel",
            wraplength=360,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

    def _build_reference_box(self, parent) -> None:
        frame = self._labelframe(parent, "Rb87 Reference")
        refs = [
            ("Transition", "Rb87 D2, 780.241209 nm"),
            ("Linewidth", "6.065 MHz"),
            ("|gF|", "0.5 (effective ground-state scale)"),
            ("Model type", "Semi-empirical PGC suppression + thermal relaxation"),
        ]
        for label, value in refs:
            row = ttk.Frame(frame, style="Panel.TFrame")
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{label}:", width=16).pack(side="left", anchor="w")
            ttk.Label(row, text=value, style="Muted.TLabel", wraplength=220, justify="left").pack(side="left", anchor="w")

    def _var_spin(self, master, var, from_, to, increment, width=10):
        spin = tk.Spinbox(
            master,
            from_=from_,
            to=to,
            increment=increment,
            textvariable=var,
            width=width,
            relief="solid",
            borderwidth=1,
            highlightthickness=0,
            bg="#fbfaf7",
        )
        return spin

    def _build_field_group(self, parent):
        frame = self._labelframe(parent, "Residual Magnetic Fields")
        vars_map = {}
        headers = ["", "X", "Y", "Z"]
        for col, label in enumerate(headers):
            ttk.Label(frame, text=label, style="Muted.TLabel").grid(row=0, column=col, padx=4, pady=3, sticky="w")

        static_vars = {}
        ttk.Label(frame, text="Static stray field").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        for col, axis in enumerate(("x", "y", "z"), start=1):
            var = tk.DoubleVar(value=0.0)
            spin = self._var_spin(frame, var, -5000, 5000, 1.0)
            spin.grid(row=1, column=col, padx=4, pady=3, sticky="ew")
            var.trace_add("write", lambda *_: self.update_derived_labels())
            static_vars[axis] = var

        switch_vars = {}
        ttk.Label(frame, text="Switch-off residual").grid(row=2, column=0, sticky="w", padx=4, pady=3)
        for col, axis in enumerate(("x", "y", "z"), start=1):
            var = tk.DoubleVar(value=0.0)
            spin = self._var_spin(frame, var, -5000, 5000, 1.0)
            spin.grid(row=2, column=col, padx=4, pady=3, sticky="ew")
            var.trace_add("write", lambda *_: self.update_derived_labels())
            switch_vars[axis] = var

        decay_var = tk.DoubleVar(value=1.8)
        decay_var.trace_add("write", lambda *_: self.update_derived_labels())
        ttk.Label(frame, text="Decay time constant (ms)").grid(row=3, column=0, sticky="w", padx=4, pady=6)
        self._var_spin(frame, decay_var, 0, 1000, 0.05).grid(row=3, column=1, columnspan=3, sticky="ew", padx=4, pady=6)

        vars_map["static"] = static_vars
        vars_map["switch"] = switch_vars
        vars_map["tau_ms"] = decay_var
        return vars_map

    def _build_molasses_group(self, parent):
        frame = self._labelframe(parent, "Molasses Model")
        specs = [
            ("initial_temperature_uK", "Initial temperature (uK)", 40.0, 0, 10000, 1.0),
            ("zero_field_temperature_uK", "Zero-field temperature (uK)", 3.0, 0, 10000, 0.5),
            ("failure_temperature_uK", "High-field failure temperature (uK)", 80.0, 0, 10000, 1.0),
            ("molasses_duration_ms", "Molasses duration (ms)", 5.0, 0.01, 1000, 0.1),
            ("time_step_us", "Time step (us)", 20.0, 0.1, 10000, 5.0),
            ("zero_field_cooling_time_ms", "Zero-field cooling time (ms)", 1.2, 0.001, 1000, 0.05),
            ("detuning_mhz", "Detuning (MHz)", -12.0, -500, 500, 0.5),
            ("saturation_parameter_per_beam", "Saturation per beam", 0.2, 0, 100, 0.02),
            ("number_of_beams", "Number of beams", 6, 1, 12, 1),
            ("optical_pumping_width_scale", "Optical-pumping width scale", 1.0, 0.001, 1000, 0.05),
            ("minimum_relative_efficiency", "Minimum relative efficiency", 0.03, 0, 1, 0.01),
        ]
        vars_map = {}
        for row, (key, label, default, start, stop, step) in enumerate(specs):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
            if key == "number_of_beams":
                var = tk.IntVar(value=default)
            else:
                var = tk.DoubleVar(value=default)
            var.trace_add("write", lambda *_: self.update_derived_labels())
            self._var_spin(frame, var, start, stop, step).grid(row=row, column=1, sticky="ew", padx=4, pady=4)
            vars_map[key] = var

        override_row = len(specs)
        self.use_width_override_var = tk.BooleanVar(value=False)
        self.use_width_override_var.trace_add("write", lambda *_: self.update_derived_labels())
        ttk.Checkbutton(frame, text="Use explicit magnetic-width override", variable=self.use_width_override_var).grid(
            row=override_row, column=0, sticky="w", padx=4, pady=4
        )
        width_override_var = tk.DoubleVar(value=0.0)
        width_override_var.trace_add("write", lambda *_: self.update_derived_labels())
        self._var_spin(frame, width_override_var, 0, 10000, 1.0).grid(row=override_row, column=1, sticky="ew", padx=4, pady=4)
        vars_map["magnetic_width_mG_override"] = width_override_var
        return vars_map

    def _build_geometry_group(self, parent):
        frame = self._labelframe(parent, "Coil Geometry")
        vars_map = {}
        specs = [
            ("turns_per_coil", "Turns per coil", 15, 1, 500, 1),
            ("side_length_cm", "Square side length (cm)", 30.0, 0.1, 500, 1.0),
            ("center_to_coil_cm", "Center to each coil (cm)", 20.0, 0.1, 500, 1.0),
        ]
        for row, (key, label, default, start, stop, step) in enumerate(specs):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
            var = tk.IntVar(value=default) if key == "turns_per_coil" else tk.DoubleVar(value=default)
            var.trace_add("write", lambda *_: self.update_derived_labels())
            self._var_spin(frame, var, start, stop, step).grid(row=row, column=1, sticky="ew", padx=4, pady=4)
            vars_map[key] = var
        return vars_map

    def _build_scan_group(self, parent):
        frame = self._labelframe(parent, "Coarse Current Scan")
        for col, text in enumerate(["", "Start (A)", "Stop (A)", "Points"]):
            ttk.Label(frame, text=text, style="Muted.TLabel").grid(row=0, column=col, sticky="w", padx=4, pady=3)
        vars_map = {}
        for row, axis in enumerate(("x", "y", "z"), start=1):
            ttk.Label(frame, text=f"{axis.upper()} current").grid(row=row, column=0, sticky="w", padx=4, pady=4)
            start_var = tk.DoubleVar(value=-1.0)
            stop_var = tk.DoubleVar(value=1.0)
            points_var = tk.IntVar(value=25)
            for var in (start_var, stop_var, points_var):
                var.trace_add("write", lambda *_: self.update_derived_labels())
            self._var_spin(frame, start_var, -50, 50, 0.1, width=9).grid(row=row, column=1, padx=4, pady=4)
            self._var_spin(frame, stop_var, -50, 50, 0.1, width=9).grid(row=row, column=2, padx=4, pady=4)
            self._var_spin(frame, points_var, 2, 2000, 1, width=8).grid(row=row, column=3, padx=4, pady=4)
            vars_map[axis] = {"start": start_var, "stop": stop_var, "points": points_var}
        return vars_map

    def _build_refinement_group(self, parent):
        frame = self._labelframe(parent, "Overview Resolution and Refinement")
        vars_map = {
            "enabled": tk.BooleanVar(value=True),
            "steps": tk.IntVar(value=1),
            "points_per_axis": tk.IntVar(value=15),
            "target_step_A": tk.DoubleVar(value=0.01),
        }
        for var in vars_map.values():
            var.trace_add("write", lambda *_: self.update_derived_labels())
        ttk.Checkbutton(frame, text="Enable local refinement", variable=vars_map["enabled"]).grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=4)
        ttk.Label(frame, text="Max refinement stages").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self._var_spin(frame, vars_map["steps"], 1, 10, 1).grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(frame, text="Minimum points per axis").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self._var_spin(frame, vars_map["points_per_axis"], 3, 4000, 2).grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(frame, text="Target overview step (A)").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        self._var_spin(frame, vars_map["target_step_A"], 0.0001, 10.0, 0.005).grid(row=3, column=1, sticky="ew", padx=4, pady=4)
        return vars_map

    def _build_output_group(self, parent):
        frame = self._labelframe(parent, "Output Naming")
        directory_var = tk.StringVar(value="outputs")
        prefix_var = tk.StringVar(value="rb87_pgc_current_scan")
        directory_var.trace_add("write", lambda *_: self.update_derived_labels())
        prefix_var.trace_add("write", lambda *_: self.update_derived_labels())
        ttk.Label(frame, text="Output directory").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(frame, textvariable=directory_var).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(frame, text="File prefix").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(frame, textvariable=prefix_var).grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        frame.columnconfigure(1, weight=1)
        return {"directory": directory_var, "prefix": prefix_var}

    def _build_derived_group(self, parent):
        frame = self._labelframe(parent, "Derived Quantities")
        labels = []
        for _ in range(3):
            label = ttk.Label(frame, text="--", style="Muted.TLabel", wraplength=360, justify="left")
            label.pack(fill="x", pady=4)
            labels.append(label)
        return labels

    def _build_right_panel(self, parent) -> None:
        metrics_row = ttk.Frame(parent, style="App.TFrame")
        metrics_row.pack(fill="x", pady=(0, 10))
        self.metric_labels = {}
        for key, title in (
            ("temperature", "Final Temperature"),
            ("current", "Best Current Setpoint"),
            ("field", "Compensation Field"),
            ("resolution", "Overview Grid Step"),
        ):
            card = ttk.Frame(metrics_row, style="Card.TFrame", padding=(14, 12))
            card.pack(side="left", fill="x", expand=True, padx=5)
            ttk.Label(card, text=title, style="MetricTitle.TLabel").pack(anchor="w")
            value_label = ttk.Label(card, text="--", style="MetricValue.TLabel", wraplength=240, justify="left")
            value_label.pack(anchor="w", pady=(4, 2))
            detail_label = ttk.Label(card, text="", style="MetricDetail.TLabel", wraplength=240, justify="left")
            detail_label.pack(anchor="w")
            self.metric_labels[key] = (value_label, detail_label)

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True)

        self.overview_panel = InteractivePlotPanel(
            self.notebook,
            "Overview Map",
            "Temperature slices across the best current neighborhood. This panel uses the final refined grid whenever refinement is enabled.",
        )
        self.dynamics_panel = InteractivePlotPanel(
            self.notebook,
            "Dynamics Trace",
            "Residual magnetic-field evolution and temperature trajectory during optical molasses.",
        )
        self.summary_text = tk.Text(self.notebook, wrap="word", bg="#ffffff", fg="#16252d", relief="solid", borderwidth=1)
        self.outputs_text = tk.Text(self.notebook, wrap="word", bg="#ffffff", fg="#16252d", relief="solid", borderwidth=1)
        self.model_text = tk.Text(self.notebook, wrap="word", bg="#ffffff", fg="#16252d", relief="solid", borderwidth=1)

        self._set_text(self.summary_text, "Run a simulation to populate the summary report.")
        self._set_text(self.outputs_text, "Run a simulation to see generated output files.")
        self._set_text(self.model_text, self._model_notes_text())

        self.notebook.add(self.overview_panel, text="Overview")
        self.notebook.add(self.dynamics_panel, text="Dynamics")
        self.notebook.add(self.summary_text, text="Summary")
        self.notebook.add(self.outputs_text, text="Outputs")
        self.notebook.add(self.model_text, text="Model")

    def _set_text(self, widget: tk.Text, value: str) -> None:
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.config(state="disabled")

    def _model_notes_text(self) -> str:
        return (
            "Model Notes\n\n"
            "This UI uses the same simulation core as the command-line tool. It is designed for experimental scan planning and calibration, not as a full quantum-optical Monte Carlo solver.\n\n"
            "Residual field model:\n"
            "B(t) = B_stray + B_coil + B_switch_off exp(-t / tau)\n\n"
            "Cooling-efficiency suppression:\n"
            "eta(t) = 1 / [1 + (|B(t)| / B_width)^2]\n\n"
            "Temperature evolution:\n"
            "dT/dt = -(T - T_eq(B)) / tau_cool(B)\n\n"
            "Key interpretation:\n"
            "- Static stray field is the long-lived background field after switch-off transients vanish.\n"
            "- Switch-off residual field is the transient field present at the beginning of molasses.\n"
            "- Target overview step controls the final current-grid spacing shown in the overview figure when local refinement is enabled.\n"
        )

    def current_config(self) -> core.SimulationConfig:
        width_override = None
        if self.use_width_override_var.get():
            width_override = float(self.molasses_vars["magnetic_width_mG_override"].get())
        return core.SimulationConfig(
            atom=core.AtomConfig(),
            molasses=core.MolassesConfig(
                initial_temperature_uK=float(self.molasses_vars["initial_temperature_uK"].get()),
                zero_field_temperature_uK=float(self.molasses_vars["zero_field_temperature_uK"].get()),
                failure_temperature_uK=float(self.molasses_vars["failure_temperature_uK"].get()),
                molasses_duration_ms=float(self.molasses_vars["molasses_duration_ms"].get()),
                time_step_us=float(self.molasses_vars["time_step_us"].get()),
                zero_field_cooling_time_ms=float(self.molasses_vars["zero_field_cooling_time_ms"].get()),
                detuning_mhz=float(self.molasses_vars["detuning_mhz"].get()),
                saturation_parameter_per_beam=float(self.molasses_vars["saturation_parameter_per_beam"].get()),
                number_of_beams=int(self.molasses_vars["number_of_beams"].get()),
                optical_pumping_width_scale=float(self.molasses_vars["optical_pumping_width_scale"].get()),
                minimum_relative_efficiency=float(self.molasses_vars["minimum_relative_efficiency"].get()),
                magnetic_width_mG_override=width_override,
            ),
            fields=core.FieldConfig(
                static_stray_field_mG=tuple(float(self.field_vars["static"][axis].get()) for axis in ("x", "y", "z")),
                mot_switch_off_field_mG=tuple(float(self.field_vars["switch"][axis].get()) for axis in ("x", "y", "z")),
                mot_decay_tau_ms=float(self.field_vars["tau_ms"].get()),
            ),
            coil_geometry=core.CoilGeometryConfig(
                turns_per_coil=int(self.geometry_vars["turns_per_coil"].get()),
                side_length_cm=float(self.geometry_vars["side_length_cm"].get()),
                center_to_coil_cm=float(self.geometry_vars["center_to_coil_cm"].get()),
            ),
            scan=core.CurrentScanConfig(
                x_current_A=core.AxisScan(
                    start=float(self.scan_vars["x"]["start"].get()),
                    stop=float(self.scan_vars["x"]["stop"].get()),
                    points=int(self.scan_vars["x"]["points"].get()),
                ),
                y_current_A=core.AxisScan(
                    start=float(self.scan_vars["y"]["start"].get()),
                    stop=float(self.scan_vars["y"]["stop"].get()),
                    points=int(self.scan_vars["y"]["points"].get()),
                ),
                z_current_A=core.AxisScan(
                    start=float(self.scan_vars["z"]["start"].get()),
                    stop=float(self.scan_vars["z"]["stop"].get()),
                    points=int(self.scan_vars["z"]["points"].get()),
                ),
            ),
            refinement=core.RefinementConfig(
                enabled=bool(self.refinement_vars["enabled"].get()),
                steps=int(self.refinement_vars["steps"].get()),
                points_per_axis=int(self.refinement_vars["points_per_axis"].get()),
                target_step_A=float(self.refinement_vars["target_step_A"].get()),
            ),
            output=core.OutputConfig(
                directory=self.output_vars["directory"].get().strip() or "outputs",
                prefix=self.output_vars["prefix"].get().strip() or "rb87_pgc_current_scan",
            ),
        )

    def apply_config(self, config: core.SimulationConfig) -> None:
        for axis, value in zip(("x", "y", "z"), config.fields.static_stray_field_mG):
            self.field_vars["static"][axis].set(value)
        for axis, value in zip(("x", "y", "z"), config.fields.mot_switch_off_field_mG):
            self.field_vars["switch"][axis].set(value)
        self.field_vars["tau_ms"].set(config.fields.mot_decay_tau_ms)

        mol = config.molasses
        self.molasses_vars["initial_temperature_uK"].set(mol.initial_temperature_uK)
        self.molasses_vars["zero_field_temperature_uK"].set(mol.zero_field_temperature_uK)
        self.molasses_vars["failure_temperature_uK"].set(mol.failure_temperature_uK)
        self.molasses_vars["molasses_duration_ms"].set(mol.molasses_duration_ms)
        self.molasses_vars["time_step_us"].set(mol.time_step_us)
        self.molasses_vars["zero_field_cooling_time_ms"].set(mol.zero_field_cooling_time_ms)
        self.molasses_vars["detuning_mhz"].set(mol.detuning_mhz)
        self.molasses_vars["saturation_parameter_per_beam"].set(mol.saturation_parameter_per_beam)
        self.molasses_vars["number_of_beams"].set(mol.number_of_beams)
        self.molasses_vars["optical_pumping_width_scale"].set(mol.optical_pumping_width_scale)
        self.molasses_vars["minimum_relative_efficiency"].set(mol.minimum_relative_efficiency)
        self.use_width_override_var.set(mol.magnetic_width_mG_override is not None)
        self.molasses_vars["magnetic_width_mG_override"].set(0.0 if mol.magnetic_width_mG_override is None else mol.magnetic_width_mG_override)

        self.geometry_vars["turns_per_coil"].set(config.coil_geometry.turns_per_coil)
        self.geometry_vars["side_length_cm"].set(config.coil_geometry.side_length_cm)
        self.geometry_vars["center_to_coil_cm"].set(config.coil_geometry.center_to_coil_cm)

        for axis, axis_scan in zip(("x", "y", "z"), (config.scan.x_current_A, config.scan.y_current_A, config.scan.z_current_A)):
            self.scan_vars[axis]["start"].set(axis_scan.start)
            self.scan_vars[axis]["stop"].set(axis_scan.stop)
            self.scan_vars[axis]["points"].set(axis_scan.points)

        self.refinement_vars["enabled"].set(config.refinement.enabled)
        self.refinement_vars["steps"].set(config.refinement.steps)
        self.refinement_vars["points_per_axis"].set(config.refinement.points_per_axis)
        self.refinement_vars["target_step_A"].set(config.refinement.target_step_A)

        self.output_vars["directory"].set(config.output.directory)
        self.output_vars["prefix"].set(config.output.prefix)
        self.update_derived_labels()

    def update_derived_labels(self) -> None:
        try:
            config = self.current_config()
        except Exception:
            return
        field_per_amp = core.square_pair_center_field_mG_per_A(config.coil_geometry)
        magnetic_width = core.magnetic_width_mG(config)

        coarse_steps = {
            "x": core.axis_step(config.scan.x_current_A.values()),
            "y": core.axis_step(config.scan.y_current_A.values()),
            "z": core.axis_step(config.scan.z_current_A.values()),
        }
        if config.refinement.enabled:
            overview_step = min(config.refinement.target_step_A, max(coarse_steps.values()))
            note = (
                f"Refinement enabled, target overview step <= {config.refinement.target_step_A:.4f} A "
                f"with up to {config.refinement.steps} stage(s)."
            )
        else:
            overview_step = max(coarse_steps.values())
            note = "Refinement disabled, overview figure will use the coarse-grid step."

        self.derived_labels[0].config(
            text=(
                "Center-field conversion\n"
                f"1 A -> {field_per_amp:.6f} mG for each ideal axis pair\n"
                f"Geometry: {config.coil_geometry.turns_per_coil} turns, "
                f"{config.coil_geometry.side_length_cm:.2f} cm square, "
                f"{config.coil_geometry.center_to_coil_cm:.2f} cm offset."
            )
        )
        self.derived_labels[1].config(
            text=(
                "Cooling-width estimate\n"
                f"Magnetic width B_width = {magnetic_width:.6f} mG\n"
                f"Detuning = {config.molasses.detuning_mhz:.3f} MHz, "
                f"s_per_beam = {config.molasses.saturation_parameter_per_beam:.4f}, "
                f"beams = {config.molasses.number_of_beams}."
            )
        )
        self.derived_labels[2].config(
            text=(
                "Scan and overview resolution\n"
                f"Coarse steps: dIx = {coarse_steps['x']:.4f} A, dIy = {coarse_steps['y']:.4f} A, dIz = {coarse_steps['z']:.4f} A\n"
                f"Expected overview step: about {overview_step:.4f} A\n"
                f"{note}"
            )
        )

    def run_simulation(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showinfo("Simulation Running", "A simulation is already in progress.")
            return
        self.run_button.state(["disabled"])
        self.progress.start(10)
        self.status_var.set("Preparing simulation...")
        self.worker = SimulationThread(self.current_config(), self.result_queue)
        self.worker.start()

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.result_queue.get_nowait()
                if kind == "status":
                    self.status_var.set(payload)
                elif kind == "result":
                    self._handle_result(payload)
                elif kind == "error":
                    self._handle_error(payload)
        except queue.Empty:
            pass
        self.root.after(120, self._poll_queue)

    def _handle_result(self, bundle: dict) -> None:
        self.last_bundle = bundle
        self.run_button.state(["!disabled"])
        self.progress.stop()
        self.status_var.set("Simulation complete.")

        config = bundle["config"]
        best_result = bundle["best_result"]
        refinement_result = bundle["refinement_result"]
        coarse_result = bundle["coarse_result"]

        self.overview_panel.draw_overview(config, coarse_result, best_result, refinement_result)
        self.overview_panel.set_export_path(bundle["paths"]["overview"])
        self.dynamics_panel.draw_dynamics(config, best_result)
        self.dynamics_panel.set_export_path(bundle["paths"]["dynamics"])

        summary_text = Path(bundle["paths"]["summary"]).read_text(encoding="utf-8")
        self._set_text(self.summary_text, summary_text)
        self._set_text(self.outputs_text, self._outputs_text(bundle))

        field_per_amp = core.square_pair_center_field_mG_per_A(config.coil_geometry)
        coarse_step_x = core.axis_step(coarse_result["x_currents"])
        if refinement_result is not None and refinement_result.get("final_grid") is not None:
            final_grid = refinement_result["final_grid"]
            overview_step = max(
                core.axis_step(final_grid["x_currents"]),
                core.axis_step(final_grid["y_currents"]),
                core.axis_step(final_grid["z_currents"]),
            )
        else:
            overview_step = coarse_step_x

        self.metric_labels["temperature"][0].config(text=f"{best_result['final_temperature_uK']:.4f} uK")
        self.metric_labels["temperature"][1].config(text=f"Cooling efficiency = {best_result['cooling_efficiency']:.4f}")

        self.metric_labels["current"][0].config(
            text=f"({best_result['current_xyz_A'][0]:.4f}, {best_result['current_xyz_A'][1]:.4f}, {best_result['current_xyz_A'][2]:.4f}) A"
        )
        self.metric_labels["current"][1].config(text="Best current triplet from the final search grid.")

        self.metric_labels["field"][0].config(
            text=f"({best_result['coil_field_mG'][0]:.2f}, {best_result['coil_field_mG'][1]:.2f}, {best_result['coil_field_mG'][2]:.2f}) mG"
        )
        self.metric_labels["field"][1].config(text=f"Center-field conversion = {field_per_amp:.3f} mG/A")

        self.metric_labels["resolution"][0].config(text=f"{overview_step:.4f} A")
        self.metric_labels["resolution"][1].config(text=f"Coarse dI = {coarse_step_x:.4f} A; overview uses the final grid.")

        self.notebook.select(self.overview_panel)

    def _handle_error(self, trace_text: str) -> None:
        self.run_button.state(["!disabled"])
        self.progress.stop()
        self.status_var.set("Simulation failed.")
        messagebox.showerror("Simulation Failed", trace_text)

    def _outputs_text(self, bundle: dict) -> str:
        lines = [
            "Generated Outputs",
            "",
            "The GUI writes the same outputs as the command-line version.",
            "",
        ]
        for label, key in (
            ("Output directory", "output_dir"),
            ("Coarse scan CSV", "csv"),
            ("Refined scan CSV", "refined_csv"),
            ("Overview figure", "overview"),
            ("Dynamics figure", "dynamics"),
            ("Summary text", "summary"),
            ("Resolved config", "resolved_config"),
        ):
            path = bundle["paths"].get(key)
            if path is not None:
                lines.append(f"{label}: {path}")
        return "\n".join(lines)

    def load_config_dialog(self) -> None:
        path_text = filedialog.askopenfilename(
            title="Load Simulation Config",
            initialdir=str(Path(core.__file__).resolve().parent),
            filetypes=[("JSON Files", "*.json")],
        )
        if not path_text:
            return
        config = core.load_config(Path(path_text))
        self.apply_config(config)
        self.status_var.set(f"Loaded config: {path_text}")

    def save_config_dialog(self) -> None:
        path_text = filedialog.asksaveasfilename(
            title="Save Simulation Config",
            initialdir=str(Path(core.__file__).resolve().parent),
            initialfile="ui_config.json",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
        )
        if not path_text:
            return
        Path(path_text).write_text(json.dumps(asdict(self.current_config()), indent=2), encoding="utf-8")
        self.status_var.set(f"Saved config: {path_text}")

    def open_output_directory(self) -> None:
        if self.last_bundle is not None:
            path = self.last_bundle["paths"]["output_dir"]
        else:
            path = Path(core.__file__).resolve().parent / self.current_config().output.directory
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)


def launch() -> int:
    root = tk.Tk()
    app = TkBiasCoilsApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(launch())
