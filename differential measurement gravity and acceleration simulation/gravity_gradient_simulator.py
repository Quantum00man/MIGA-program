from __future__ import annotations

import math
import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib

matplotlib.use("TkAgg")

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np

from miga_physics import (
    SourceMass,
    acceleration_gradient,
    background_gravity_projection_on_bragg,
    beam_acceleration_to_angular_frequency,
    beam_acceleration_to_x_axis_after_gravity_subtraction,
    differential_acceleration,
    first_order_bragg_keff,
    fixed_position_mass_scan,
    fringe_period_to_beam_acceleration,
    fringe_signal,
    horizontal_gradiometer_points,
    remove_background_gravity_from_beam_acceleration,
    required_mass_profile_for_target_gradient,
    response_from_source_mass,
    angular_frequency_to_beam_acceleration,
)


class GravityGradientApp(tk.Tk):
    PERIOD_MODE = "Fringe period"
    OMEGA_MODE = "Angular frequency"

    def __init__(self) -> None:
        super().__init__()
        self.title("Horizontal Bragg Gradiometer Designer")
        self.geometry("1580x980")
        self.minsize(1380, 860)

        self.configure(bg="#f4f4ef")
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#f4f4ef")
        self.style.configure("TLabelframe", background="#f4f4ef", bordercolor="#b9b29f")
        self.style.configure("TLabelframe.Label", background="#f4f4ef", foreground="#23211d")
        self.style.configure("TLabel", background="#f4f4ef", foreground="#23211d")
        self.style.configure("TButton", padding=6)
        self.style.configure("Treeview", rowheight=28)
        self.style.configure("Treeview.Heading", font=("TkDefaultFont", 10, "bold"))

        self._build_variables()
        self._build_layout()
        self._update_mode_controls()
        self.compute()

    def _build_variables(self) -> None:
        self.baseline_var = tk.StringVar(value="2.0")
        self.wavelength_nm_var = tk.StringVar(value="780.24")
        self.alpha_mrad_var = tk.StringVar(value="1.28")
        self.gravity_m_s2_var = tk.StringVar(value="9.81")

        self.mass_var = tk.StringVar(value="2000")
        self.mass_x_var = tk.StringVar(value="1.20")
        self.mass_y_var = tk.StringVar(value="0.80")

        self.mode_var = tk.StringVar(value=self.PERIOD_MODE)
        self.unit_var = tk.StringVar(value="s^2")
        self.sign_21_var = tk.StringVar(value="+1")
        self.sign_22_var = tk.StringVar(value="+1")
        self.fringe_21_var = tk.StringVar(value="5.60")
        self.fringe_22_var = tk.StringVar(value="6.15")

        self.phase_21_var = tk.StringVar(value="0.00")
        self.phase_22_var = tk.StringVar(value="0.55")
        self.contrast_21_var = tk.StringVar(value="0.85")
        self.contrast_22_var = tk.StringVar(value="0.82")
        self.scan_min_var = tk.StringVar(value="0")
        self.scan_max_var = tk.StringVar(value="7000")

        self.design_x_min_var = tk.StringVar(value="-3.0")
        self.design_x_max_var = tk.StringVar(value="5.0")
        self.design_points_var = tk.StringVar(value="500")

        self.mass_scan_max_var = tk.StringVar(value="5000")
        self.mass_scan_points_var = tk.StringVar(value="300")

        self.keff_summary_var = tk.StringVar()
        self.summary_var = tk.StringVar()
        self.hover_var = tk.StringVar(value="Interactive plot: use pan/zoom toolbar or hover over a subplot.")

    def _build_layout(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=0)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(0, weight=1)

        controls = ttk.Frame(outer)
        controls.grid(row=0, column=0, sticky="nsw", padx=(0, 14))

        main = ttk.Frame(outer)
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        self._build_control_panel(controls)
        self._build_results_panel(main)
        self._build_figure_panel(main)

    def _build_control_panel(self, parent: ttk.Frame) -> None:
        title = ttk.Label(
            parent,
            text=(
                "Horizontal shared-beam atom gradiometer\n"
                "MIGA21 at x = 0 m, MIGA22 at x = L"
            ),
            justify="left",
            font=("TkDefaultFont", 12, "bold"),
        )
        title.pack(anchor="w", pady=(0, 10))

        geometry_frame = ttk.LabelFrame(parent, text="Geometry and Bragg axis", padding=10)
        geometry_frame.pack(fill="x", pady=(0, 10))
        self._add_labeled_entry(geometry_frame, "Baseline L (m)", self.baseline_var, 0)
        self._add_labeled_entry(geometry_frame, "Bragg wavelength (nm)", self.wavelength_nm_var, 1)
        self._add_labeled_entry(geometry_frame, "Tilt alpha (mrad)", self.alpha_mrad_var, 2)
        self._add_labeled_entry(geometry_frame, "Background |g| (m/s^2)", self.gravity_m_s2_var, 3)

        source_frame = ttk.LabelFrame(parent, text="Current source-mass model", padding=10)
        source_frame.pack(fill="x", pady=(0, 10))
        self._add_labeled_entry(source_frame, "Source mass (kg)", self.mass_var, 0)
        self._add_labeled_entry(source_frame, "Source position x (m)", self.mass_x_var, 1)
        self._add_labeled_entry(source_frame, "Source position y (m)", self.mass_y_var, 2)

        fringe_frame = ttk.LabelFrame(parent, text="Fringe inversion", padding=10)
        fringe_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(fringe_frame, text="Input mode").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        mode_box = ttk.Combobox(
            fringe_frame,
            textvariable=self.mode_var,
            state="readonly",
            values=[self.PERIOD_MODE, self.OMEGA_MODE],
            width=20,
        )
        mode_box.grid(row=0, column=1, sticky="ew", pady=4)
        mode_box.bind("<<ComboboxSelected>>", lambda _event: self._update_mode_controls())

        ttk.Label(fringe_frame, text="Input unit").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.unit_box = ttk.Combobox(fringe_frame, textvariable=self.unit_var, state="readonly", width=20)
        self.unit_box.grid(row=1, column=1, sticky="ew", pady=4)

        self.fringe_label = ttk.Label(fringe_frame, text="Fringe quantity")
        self.fringe_label.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)

        ttk.Label(fringe_frame, text="MIGA21").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(fringe_frame, textvariable=self.fringe_21_var, width=20).grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Label(fringe_frame, text="MIGA22").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(fringe_frame, textvariable=self.fringe_22_var, width=20).grid(row=4, column=1, sticky="ew", pady=4)

        ttk.Label(fringe_frame, text="Period sign for MIGA21").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=4)
        self.sign_21_box = ttk.Combobox(
            fringe_frame,
            textvariable=self.sign_21_var,
            state="readonly",
            values=["+1", "-1"],
            width=20,
        )
        self.sign_21_box.grid(row=5, column=1, sticky="ew", pady=4)

        ttk.Label(fringe_frame, text="Period sign for MIGA22").grid(row=6, column=0, sticky="w", padx=(0, 8), pady=4)
        self.sign_22_box = ttk.Combobox(
            fringe_frame,
            textvariable=self.sign_22_var,
            state="readonly",
            values=["+1", "-1"],
            width=20,
        )
        self.sign_22_box.grid(row=6, column=1, sticky="ew", pady=4)

        scan_frame = ttk.LabelFrame(parent, text="Synthetic T^2 scan", padding=10)
        scan_frame.pack(fill="x", pady=(0, 10))
        self._add_labeled_entry(scan_frame, "Phase offset MIGA21 (rad)", self.phase_21_var, 0)
        self._add_labeled_entry(scan_frame, "Phase offset MIGA22 (rad)", self.phase_22_var, 1)
        self._add_labeled_entry(scan_frame, "Contrast MIGA21", self.contrast_21_var, 2)
        self._add_labeled_entry(scan_frame, "Contrast MIGA22", self.contrast_22_var, 3)
        self._add_labeled_entry(scan_frame, "Scan min T^2 (ms^2)", self.scan_min_var, 4)
        self._add_labeled_entry(scan_frame, "Scan max T^2 (ms^2)", self.scan_max_var, 5)

        design_frame = ttk.LabelFrame(parent, text="Inverse design: object constrained to y = 0", padding=10)
        design_frame.pack(fill="x", pady=(0, 10))
        self._add_labeled_entry(design_frame, "Design x min (m)", self.design_x_min_var, 0)
        self._add_labeled_entry(design_frame, "Design x max (m)", self.design_x_max_var, 1)
        self._add_labeled_entry(design_frame, "Design samples", self.design_points_var, 2)

        mass_scan_frame = ttk.LabelFrame(parent, text="Fixed-position mass scan", padding=10)
        mass_scan_frame.pack(fill="x", pady=(0, 10))
        self._add_labeled_entry(mass_scan_frame, "Mass scan max (kg)", self.mass_scan_max_var, 0)
        self._add_labeled_entry(mass_scan_frame, "Mass scan samples", self.mass_scan_points_var, 1)

        button_frame = ttk.Frame(parent)
        button_frame.pack(fill="x", pady=(4, 8))
        ttk.Button(button_frame, text="Compute", command=self.compute).pack(side="left")
        ttk.Button(button_frame, text="Reset defaults", command=self._reset_defaults).pack(side="left", padx=(8, 0))

        note = ttk.Label(
            parent,
            text=(
                "Fringes are first inverted into total acceleration along the Bragg axis.\n"
                "The Bragg projection of the background gravity is subtracted before the x-axis acceleration is reported."
            ),
            justify="left",
            wraplength=380,
        )
        note.pack(anchor="w", pady=(8, 0))

    def _build_results_panel(self, parent: ttk.Frame) -> None:
        results_frame = ttk.LabelFrame(parent, text="Computed quantities", padding=10)
        results_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        results_frame.columnconfigure(0, weight=1)

        columns = (
            "instrument",
            "position",
            "model_ax",
            "model_ay",
            "model_bragg",
            "model_x",
            "fringe_bragg_total",
            "gravity_bragg",
            "fringe_bragg_net",
            "fringe_x",
        )
        self.result_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=3)
        headings = {
            "instrument": "Instrument",
            "position": "x position (m)",
            "model_ax": "Model a_x (m/s^2)",
            "model_ay": "Model a_y (m/s^2)",
            "model_bragg": "Model a_B (m/s^2)",
            "model_x": "Model x-est. (m/s^2)",
            "fringe_bragg_total": "Fringe a_B total (m/s^2)",
            "gravity_bragg": "Gravity a_g,B (m/s^2)",
            "fringe_bragg_net": "Fringe a_B net (m/s^2)",
            "fringe_x": "Fringe corrected a_x (m/s^2)",
        }
        widths = {
            "instrument": 135,
            "position": 90,
            "model_ax": 150,
            "model_ay": 150,
            "model_bragg": 150,
            "model_x": 150,
            "fringe_bragg_total": 170,
            "gravity_bragg": 165,
            "fringe_bragg_net": 165,
            "fringe_x": 180,
        }
        for key in columns:
            self.result_tree.heading(key, text=headings[key])
            self.result_tree.column(key, width=widths[key], anchor="center")
        self.result_tree.grid(row=0, column=0, sticky="ew")

        scrollbar = ttk.Scrollbar(results_frame, orient="horizontal", command=self.result_tree.xview)
        scrollbar.grid(row=1, column=0, sticky="ew")
        self.result_tree.configure(xscrollcommand=scrollbar.set)

        ttk.Label(results_frame, textvariable=self.keff_summary_var, font=("TkDefaultFont", 10, "bold")).grid(
            row=2, column=0, sticky="w", pady=(8, 2)
        )
        ttk.Label(results_frame, textvariable=self.summary_var, justify="left", wraplength=1040).grid(
            row=3, column=0, sticky="w"
        )
        ttk.Label(results_frame, textvariable=self.hover_var, justify="left", wraplength=1040).grid(
            row=4, column=0, sticky="w", pady=(4, 0)
        )

    def _build_figure_panel(self, parent: ttk.Frame) -> None:
        figure_frame = ttk.LabelFrame(parent, text="Interactive plots", padding=8)
        figure_frame.grid(row=1, column=0, sticky="nsew")
        figure_frame.rowconfigure(0, weight=1)
        figure_frame.columnconfigure(0, weight=1)

        self.figure = Figure(figsize=(11.0, 7.8), facecolor="#fbfaf6")
        self.ax_geometry = self.figure.add_subplot(221)
        self.ax_fringe = self.figure.add_subplot(222)
        self.ax_design = self.figure.add_subplot(223)
        self.ax_scan = self.figure.add_subplot(224)
        self.ax_scan_grad = self.ax_scan.twinx()
        self.figure.subplots_adjust(hspace=0.34, wspace=0.28, left=0.06, right=0.97, top=0.95, bottom=0.08)

        self.canvas = FigureCanvasTkAgg(self.figure, master=figure_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        toolbar_frame = ttk.Frame(figure_frame)
        toolbar_frame.grid(row=1, column=0, sticky="ew")
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side="left")

        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("pick_event", self._on_pick)

    def _add_labeled_entry(self, parent: ttk.LabelFrame, label_text: str, variable: tk.StringVar, row: int) -> None:
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(parent, textvariable=variable, width=20).grid(row=row, column=1, sticky="ew", pady=4)

    def _reset_defaults(self) -> None:
        self.baseline_var.set("2.0")
        self.wavelength_nm_var.set("780.24")
        self.alpha_mrad_var.set("1.28")
        self.gravity_m_s2_var.set("9.81")
        self.mass_var.set("2000")
        self.mass_x_var.set("1.20")
        self.mass_y_var.set("0.80")
        self.mode_var.set(self.PERIOD_MODE)
        self.unit_var.set("s^2")
        self.sign_21_var.set("+1")
        self.sign_22_var.set("+1")
        self.fringe_21_var.set("5.60")
        self.fringe_22_var.set("6.15")
        self.phase_21_var.set("0.00")
        self.phase_22_var.set("0.55")
        self.contrast_21_var.set("0.85")
        self.contrast_22_var.set("0.82")
        self.scan_min_var.set("0")
        self.scan_max_var.set("7000")
        self.design_x_min_var.set("-3.0")
        self.design_x_max_var.set("5.0")
        self.design_points_var.set("500")
        self.mass_scan_max_var.set("5000")
        self.mass_scan_points_var.set("300")
        self._update_mode_controls()
        self.compute()

    def _update_mode_controls(self) -> None:
        if self.mode_var.get() == self.PERIOD_MODE:
            self.unit_box.configure(values=["ms^2", "s^2"])
            if self.unit_var.get() not in {"ms^2", "s^2"}:
                self.unit_var.set("s^2")
            self.fringe_label.configure(text="Fringe period from T^2 scan")
            self.sign_21_box.state(["!disabled"])
            self.sign_22_box.state(["!disabled"])
        else:
            self.unit_box.configure(values=["rad/ms^2", "rad/s^2"])
            if self.unit_var.get() not in {"rad/ms^2", "rad/s^2"}:
                self.unit_var.set("rad/ms^2")
            self.fringe_label.configure(text="Angular frequency of phase versus T^2")
            self.sign_21_box.state(["disabled"])
            self.sign_22_box.state(["disabled"])

    def _parse_float(self, label: str, raw_value: str) -> float:
        try:
            return float(raw_value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a valid real number.") from exc

    def _parse_int(self, label: str, raw_value: str) -> int:
        try:
            return int(raw_value)
        except ValueError as exc:
            raise ValueError(f"{label} must be an integer.") from exc

    def _measured_beam_acceleration(self, raw_value: float, k_eff_m_inv: float, sign: float) -> float:
        if self.mode_var.get() == self.PERIOD_MODE:
            return fringe_period_to_beam_acceleration(raw_value, self.unit_var.get(), k_eff_m_inv, sign=sign)
        return angular_frequency_to_beam_acceleration(raw_value, self.unit_var.get(), k_eff_m_inv)

    def compute(self) -> None:
        try:
            baseline_m = self._parse_float("Baseline L", self.baseline_var.get())
            wavelength_nm = self._parse_float("Bragg wavelength", self.wavelength_nm_var.get())
            alpha_mrad = self._parse_float("Tilt alpha", self.alpha_mrad_var.get())
            alpha_rad = alpha_mrad * 1.0e-3
            gravity_m_s2 = self._parse_float("Background |g|", self.gravity_m_s2_var.get())

            source = SourceMass(
                mass_kg=self._parse_float("Source mass", self.mass_var.get()),
                x_m=self._parse_float("Source position x", self.mass_x_var.get()),
                y_m=self._parse_float("Source position y", self.mass_y_var.get()),
            )

            fringe_21 = self._parse_float("MIGA21 fringe input", self.fringe_21_var.get())
            fringe_22 = self._parse_float("MIGA22 fringe input", self.fringe_22_var.get())
            phase_21 = self._parse_float("MIGA21 phase offset", self.phase_21_var.get())
            phase_22 = self._parse_float("MIGA22 phase offset", self.phase_22_var.get())
            contrast_21 = self._parse_float("MIGA21 contrast", self.contrast_21_var.get())
            contrast_22 = self._parse_float("MIGA22 contrast", self.contrast_22_var.get())
            scan_min_ms2 = self._parse_float("Scan min T^2", self.scan_min_var.get())
            scan_max_ms2 = self._parse_float("Scan max T^2", self.scan_max_var.get())
            sign_21 = float(self.sign_21_var.get())
            sign_22 = float(self.sign_22_var.get())

            design_x_min = self._parse_float("Design x min", self.design_x_min_var.get())
            design_x_max = self._parse_float("Design x max", self.design_x_max_var.get())
            design_points = self._parse_int("Design samples", self.design_points_var.get())

            mass_scan_max = self._parse_float("Mass scan max", self.mass_scan_max_var.get())
            mass_scan_points = self._parse_int("Mass scan samples", self.mass_scan_points_var.get())

            if not 0.0 <= contrast_21 <= 1.0 or not 0.0 <= contrast_22 <= 1.0:
                raise ValueError("Each contrast must lie between 0 and 1.")
            if source.mass_kg < 0.0:
                raise ValueError("The source mass must be non-negative.")
            if gravity_m_s2 < 0.0:
                raise ValueError("The background gravity magnitude must be non-negative.")
            if scan_max_ms2 <= scan_min_ms2:
                raise ValueError("The scan maximum must exceed the scan minimum.")
            if design_x_max <= design_x_min:
                raise ValueError("The design x maximum must exceed the design x minimum.")
            if design_points < 50:
                raise ValueError("The design sample count should be at least 50.")
            if mass_scan_max <= 0.0:
                raise ValueError("The mass scan maximum must be positive.")
            if mass_scan_points < 20:
                raise ValueError("The mass scan sample count should be at least 20.")
            if abs(math.cos(alpha_rad)) < 1.0e-12:
                raise ValueError("alpha is too close to 90 degrees for x-axis inference.")

            k_eff_m_inv = first_order_bragg_keff(wavelength_nm * 1.0e-9)
            miga21, miga22 = horizontal_gradiometer_points(baseline_m)
            response_21 = response_from_source_mass(source, miga21, alpha_rad)
            response_22 = response_from_source_mass(source, miga22, alpha_rad)

            measured_beam_total_21 = self._measured_beam_acceleration(fringe_21, k_eff_m_inv, sign_21)
            measured_beam_total_22 = self._measured_beam_acceleration(fringe_22, k_eff_m_inv, sign_22)
            gravity_beam = background_gravity_projection_on_bragg(alpha_rad, gravity_m_s2)
            measured_beam_net_21 = remove_background_gravity_from_beam_acceleration(
                measured_beam_total_21,
                alpha_rad,
                gravity_m_s2,
            )
            measured_beam_net_22 = remove_background_gravity_from_beam_acceleration(
                measured_beam_total_22,
                alpha_rad,
                gravity_m_s2,
            )
            measured_x_21 = beam_acceleration_to_x_axis_after_gravity_subtraction(
                measured_beam_total_21,
                alpha_rad,
                gravity_m_s2,
            )
            measured_x_22 = beam_acceleration_to_x_axis_after_gravity_subtraction(
                measured_beam_total_22,
                alpha_rad,
                gravity_m_s2,
            )

            delta_measured_beam = differential_acceleration(measured_beam_net_22, measured_beam_net_21)
            delta_measured_x = differential_acceleration(measured_x_22, measured_x_21)
            gradient_measured_x = acceleration_gradient(delta_measured_x, baseline_m)

            delta_model_ax = differential_acceleration(
                response_22.acceleration.ax_m_s2,
                response_21.acceleration.ax_m_s2,
            )
            delta_model_bragg = differential_acceleration(response_22.a_bragg_m_s2, response_21.a_bragg_m_s2)
            delta_model_x = differential_acceleration(response_22.a_x_estimate_m_s2, response_21.a_x_estimate_m_s2)
            gradient_model_ax = acceleration_gradient(delta_model_ax, baseline_m)
            gradient_model_x = acceleration_gradient(delta_model_x, baseline_m)

            design_positions = np.linspace(design_x_min, design_x_max, design_points)
            design = required_mass_profile_for_target_gradient(gradient_measured_x, design_positions, baseline_m)

            masses_kg = np.linspace(0.0, mass_scan_max, mass_scan_points)
            scan = fixed_position_mass_scan(masses_kg, source.x_m, source.y_m, baseline_m, alpha_rad)

            self._populate_results(
                baseline_m,
                alpha_mrad,
                gravity_m_s2,
                gravity_beam,
                k_eff_m_inv,
                miga21,
                miga22,
                response_21,
                response_22,
                measured_beam_total_21,
                measured_beam_total_22,
                measured_beam_net_21,
                measured_beam_net_22,
                measured_x_21,
                measured_x_22,
                delta_measured_beam,
                delta_measured_x,
                gradient_measured_x,
                gradient_model_ax,
                gradient_model_x,
            )
            self._update_plots(
                baseline_m,
                alpha_rad,
                source,
                k_eff_m_inv,
                miga21,
                miga22,
                response_21,
                response_22,
                gravity_beam,
                measured_beam_total_21,
                measured_beam_total_22,
                phase_21,
                phase_22,
                contrast_21,
                contrast_22,
                scan_min_ms2,
                scan_max_ms2,
                design,
                scan,
                gradient_measured_x,
            )
        except Exception as exc:
            messagebox.showerror("Invalid input", str(exc))

    def _populate_results(
        self,
        baseline_m: float,
        alpha_mrad: float,
        gravity_m_s2: float,
        gravity_beam: float,
        k_eff_m_inv: float,
        miga21,
        miga22,
        response_21,
        response_22,
        measured_beam_total_21: float,
        measured_beam_total_22: float,
        measured_beam_net_21: float,
        measured_beam_net_22: float,
        measured_x_21: float,
        measured_x_22: float,
        delta_measured_beam: float,
        delta_measured_x: float,
        gradient_measured_x: float,
        gradient_model_ax: float,
        gradient_model_x: float,
    ) -> None:
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        rows = [
            (
                "MIGA21",
                f"{miga21.x_m:.3f}",
                f"{response_21.acceleration.ax_m_s2:.6e}",
                f"{response_21.acceleration.ay_m_s2:.6e}",
                f"{response_21.a_bragg_m_s2:.6e}",
                f"{response_21.a_x_estimate_m_s2:.6e}",
                f"{measured_beam_total_21:.6e}",
                f"{gravity_beam:.6e}",
                f"{measured_beam_net_21:.6e}",
                f"{measured_x_21:.6e}",
            ),
            (
                "MIGA22",
                f"{miga22.x_m:.3f}",
                f"{response_22.acceleration.ax_m_s2:.6e}",
                f"{response_22.acceleration.ay_m_s2:.6e}",
                f"{response_22.a_bragg_m_s2:.6e}",
                f"{response_22.a_x_estimate_m_s2:.6e}",
                f"{measured_beam_total_22:.6e}",
                f"{gravity_beam:.6e}",
                f"{measured_beam_net_22:.6e}",
                f"{measured_x_22:.6e}",
            ),
            (
                "MIGA22 - MIGA21",
                f"{baseline_m:.3f}",
                f"{response_22.acceleration.ax_m_s2 - response_21.acceleration.ax_m_s2:.6e}",
                "-",
                f"{response_22.a_bragg_m_s2 - response_21.a_bragg_m_s2:.6e}",
                f"{response_22.a_x_estimate_m_s2 - response_21.a_x_estimate_m_s2:.6e}",
                f"{measured_beam_total_22 - measured_beam_total_21:.6e}",
                f"0.000000e+00",
                f"{delta_measured_beam:.6e}",
                f"{delta_measured_x:.6e}",
            ),
        ]
        for row in rows:
            self.result_tree.insert("", "end", values=row)

        omega_unit = "rad/ms^2"
        omega_21 = beam_acceleration_to_angular_frequency(measured_beam_total_21, omega_unit, k_eff_m_inv)
        omega_22 = beam_acceleration_to_angular_frequency(measured_beam_total_22, omega_unit, k_eff_m_inv)
        self.keff_summary_var.set(
            f"k_eff = {k_eff_m_inv:.6e} m^-1, alpha = {alpha_mrad:.4f} mrad, |g| = {gravity_m_s2:.5f} m/s^2, differential sign = MIGA22 - MIGA21"
        )
        self.summary_var.set(
            f"Background gravity projection on the Bragg axis = {gravity_beam:.6e} m/s^2 and is removed before x-axis inference.  "
            f"Measured corrected x-gradient from fringes = {gradient_measured_x:.6e} s^-2.  "
            f"Current source-mass actual x-gradient = {gradient_model_ax:.6e} s^-2.  "
            f"Current source-mass Bragg-equivalent x-gradient = {gradient_model_x:.6e} s^-2.\n"
            f"Because this gravity term is common-mode, the differential gradient is unchanged by the subtraction when both interferometers share the same alpha.  "
            f"Raw measured phase slopes along the Bragg axis: "
            f"MIGA21 = {omega_21:.6e} {omega_unit}, MIGA22 = {omega_22:.6e} {omega_unit}."
        )

    def _update_plots(
        self,
        baseline_m: float,
        alpha_rad: float,
        source: SourceMass,
        k_eff_m_inv: float,
        miga21,
        miga22,
        response_21,
        response_22,
        gravity_beam: float,
        measured_beam_total_21: float,
        measured_beam_total_22: float,
        phase_21: float,
        phase_22: float,
        contrast_21: float,
        contrast_22: float,
        scan_min_ms2: float,
        scan_max_ms2: float,
        design,
        scan,
        gradient_measured_x: float,
    ) -> None:
        self.ax_geometry.clear()
        self.ax_fringe.clear()
        self.ax_design.clear()
        self.ax_scan.clear()
        self.ax_scan_grad.clear()

        x_points = np.array([miga21.x_m, miga22.x_m, source.x_m], dtype=float)
        y_points = np.array([miga21.y_m, miga22.y_m, source.y_m], dtype=float)
        x_margin = max(0.35, 0.2 * (x_points.max() - x_points.min() + 1.0))
        y_margin = max(0.35, 0.25 * (y_points.max() - y_points.min() + 1.0))

        self.ax_geometry.plot([miga21.x_m, miga22.x_m], [0.0, 0.0], color="#4f6f52", lw=2.2, alpha=0.7)
        self.ax_geometry.scatter(
            [miga21.x_m, miga22.x_m],
            [miga21.y_m, miga22.y_m],
            s=110,
            color="#254e70",
            label="Atom interferometers",
            zorder=3,
        )
        self.ax_geometry.scatter(
            [source.x_m],
            [source.y_m],
            s=160,
            color="#c44536",
            marker="s",
            label="Current source mass",
            zorder=4,
        )

        beam_x = np.array([miga21.x_m - 1.2, miga22.x_m + 1.2])
        beam_y = math.tan(alpha_rad) * beam_x
        self.ax_geometry.plot(beam_x, beam_y, color="#7c6a0a", lw=1.6, ls=":", label="Bragg axis")

        arrow_scale = 0.28 * max(baseline_m, abs(source.y_m) + 0.5, 1.0)
        for point, response, label in [
            (miga21, response_21, "MIGA21"),
            (miga22, response_22, "MIGA22"),
        ]:
            magnitude = max(response.acceleration.magnitude_m_s2, 1.0e-18)
            line = self.ax_geometry.arrow(
                point.x_m,
                point.y_m,
                arrow_scale * response.acceleration.ax_m_s2 / magnitude,
                arrow_scale * response.acceleration.ay_m_s2 / magnitude,
                width=0.018,
                head_width=0.11,
                head_length=0.14,
                color="#f0a202",
                length_includes_head=True,
                zorder=2,
            )
            line.set_picker(True)
            self.ax_geometry.annotate(
                f"{label}\na_x={response.acceleration.ax_m_s2:.2e}\na_B={response.a_bragg_m_s2:.2e}",
                (point.x_m, point.y_m),
                textcoords="offset points",
                xytext=(8, 12),
                fontsize=8.5,
                color="#23211d",
            )

        self.ax_geometry.annotate(
            f"M={source.mass_kg:.3g} kg\nalpha={alpha_rad * 1.0e3:.3f} mrad",
            (source.x_m, source.y_m),
            textcoords="offset points",
            xytext=(8, 10),
            fontsize=8.5,
            color="#23211d",
        )
        self.ax_geometry.set_title("Current geometry and gravitational field", fontsize=12, weight="bold")
        self.ax_geometry.set_xlabel("x (m)")
        self.ax_geometry.set_ylabel("y (m)")
        self.ax_geometry.set_xlim(x_points.min() - x_margin, x_points.max() + x_margin)
        self.ax_geometry.set_ylim(y_points.min() - y_margin, y_points.max() + y_margin)
        self.ax_geometry.set_aspect("equal", adjustable="box")
        self.ax_geometry.grid(alpha=0.22)
        self.ax_geometry.legend(loc="upper right", frameon=False, fontsize=8.5)

        t_squared_ms2 = np.linspace(scan_min_ms2, scan_max_ms2, 700)
        trace_meas_21 = fringe_signal(t_squared_ms2, measured_beam_total_21, k_eff_m_inv, phase_21, contrast_21)
        trace_meas_22 = fringe_signal(t_squared_ms2, measured_beam_total_22, k_eff_m_inv, phase_22, contrast_22)
        trace_model_21 = fringe_signal(t_squared_ms2, response_21.a_bragg_m_s2 + gravity_beam, k_eff_m_inv, phase_21, contrast_21)
        trace_model_22 = fringe_signal(t_squared_ms2, response_22.a_bragg_m_s2 + gravity_beam, k_eff_m_inv, phase_22, contrast_22)

        for xdata, ydata, color, label, style in [
            (t_squared_ms2, trace_meas_21, "#1d3557", "MIGA21 from fringe input", "-"),
            (t_squared_ms2, trace_meas_22, "#e07a5f", "MIGA22 from fringe input", "-"),
            (t_squared_ms2, trace_model_21, "#1d3557", "MIGA21 current mass + gravity", "--"),
            (t_squared_ms2, trace_model_22, "#e07a5f", "MIGA22 current mass + gravity", "--"),
        ]:
            line, = self.ax_fringe.plot(xdata, ydata, color=color, lw=2.0 if style == "-" else 1.5, ls=style, label=label)
            line.set_picker(5)

        self.ax_fringe.set_title("Synthetic fringes versus T^2", fontsize=12, weight="bold")
        self.ax_fringe.set_xlabel("T^2 (ms^2)")
        self.ax_fringe.set_ylabel("Normalized signal")
        self.ax_fringe.grid(alpha=0.24)
        self.ax_fringe.legend(loc="upper right", frameon=False, fontsize=8.5)

        signed_line, = self.ax_design.plot(
            design.positions_x_m,
            design.required_mass_signed_kg,
            color="#6c757d",
            lw=1.6,
            ls="--",
            label="Signed equivalent mass",
        )
        signed_line.set_picker(5)
        positive_line, = self.ax_design.plot(
            design.positions_x_m,
            design.required_mass_positive_kg,
            color="#2a9d8f",
            lw=2.2,
            label="Positive mass required",
        )
        positive_line.set_picker(5)
        self.ax_design.axvline(miga21.x_m, color="#254e70", lw=1.0, ls=":")
        self.ax_design.axvline(miga22.x_m, color="#254e70", lw=1.0, ls=":")
        self.ax_design.axhline(0.0, color="#555555", lw=0.8, alpha=0.6)
        self.ax_design.set_yscale("symlog", linthresh=1.0)
        self.ax_design.set_title("Required mass on the x axis to match the measured gradient", fontsize=12, weight="bold")
        self.ax_design.set_xlabel("Source position x on y = 0 line (m)")
        self.ax_design.set_ylabel("Required mass (kg)")
        self.ax_design.grid(alpha=0.24)
        self.ax_design.legend(loc="upper right", frameon=False, fontsize=8.5)
        self.ax_design.text(
            0.02,
            0.04,
            f"Target measured x-gradient = {gradient_measured_x:.3e} s^-2",
            transform=self.ax_design.transAxes,
            fontsize=8.5,
            bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none"},
        )

        line_ax21, = self.ax_scan.plot(scan.masses_kg, scan.ax21_m_s2, color="#457b9d", lw=2.0, label="a_x at MIGA21")
        line_ax22, = self.ax_scan.plot(scan.masses_kg, scan.ax22_m_s2, color="#e76f51", lw=2.0, label="a_x at MIGA22")
        line_delta, = self.ax_scan.plot(scan.masses_kg, scan.delta_ax_m_s2, color="#5a189a", lw=1.8, ls="--", label="Delta a_x")
        line_grad, = self.ax_scan_grad.plot(scan.masses_kg, scan.gradient_ax_s2, color="#2a9d8f", lw=1.8, label="Gamma_x actual")
        line_grad_est, = self.ax_scan_grad.plot(
            scan.masses_kg,
            scan.gradient_x_estimate_s2,
            color="#bc6c25",
            lw=1.6,
            ls=":",
            label="Gamma_x inferred from Bragg",
        )
        for line in [line_ax21, line_ax22, line_delta, line_grad, line_grad_est]:
            line.set_picker(5)

        self.ax_scan.set_title("Fixed-position mass scan at the current source coordinates", fontsize=12, weight="bold")
        self.ax_scan.set_xlabel("Source mass (kg)")
        self.ax_scan.set_ylabel("Acceleration along x (m/s^2)")
        self.ax_scan_grad.set_ylabel("Gradient (s^-2)")
        self.ax_scan.grid(alpha=0.24)
        lines_left, labels_left = self.ax_scan.get_legend_handles_labels()
        lines_right, labels_right = self.ax_scan_grad.get_legend_handles_labels()
        self.ax_scan.legend(lines_left + lines_right, labels_left + labels_right, loc="upper left", frameon=False, fontsize=8.2)

        self.canvas.draw_idle()

    def _on_motion(self, event) -> None:
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            return
        title = event.inaxes.get_title() or "subplot"
        self.hover_var.set(f"Hover: {title} | x = {event.xdata:.6g}, y = {event.ydata:.6g}")

    def _on_pick(self, event) -> None:
        artist = event.artist
        label = getattr(artist, "get_label", lambda: "curve")()
        xdata = np.asarray(artist.get_xdata())
        ydata = np.asarray(artist.get_ydata())
        if xdata.size == 0:
            return
        index = int(event.ind[0]) if getattr(event, "ind", None) is not None and len(event.ind) > 0 else 0
        self.hover_var.set(f"Picked: {label} | x = {xdata[index]:.6g}, y = {ydata[index]:.6g}")


def main() -> None:
    app = GravityGradientApp()
    app.mainloop()


if __name__ == "__main__":
    main()
