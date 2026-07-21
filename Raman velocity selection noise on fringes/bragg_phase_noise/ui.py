from __future__ import annotations

import csv
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from .analysis import BraggPhaseNoiseModel, ModelOutputs, unwrap_series
from .config import AnalysisConfig, DurationConvention, EnsembleConfig, InterferometerConfig, PulseSpec
from .physics import fwhm_to_sigma

matplotlib.rcParams.update(
    {
        "axes.grid": True,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "figure.titlesize": 13,
        "font.size": 10,
        "grid.alpha": 0.25,
        "legend.fontsize": 9,
        "lines.linewidth": 2.0,
    }
)


def rad_to_mrad(values: np.ndarray | float) -> np.ndarray | float:
    return np.asarray(values) * 1.0e3


class Application(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Bragg Interferometer Phase Noise from Raman Velocity-Selection Noise")
        self.geometry("1560x940")
        self.minsize(1360, 820)

        self.variables: dict[str, tk.StringVar] = {}
        self.current_outputs: ModelOutputs | None = None

        self._build_layout()
        self._set_default_values()

    def _build_layout(self) -> None:
        outer = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        outer.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(outer, padding=10)
        right = ttk.Frame(outer, padding=10)
        outer.add(left, weight=0)
        outer.add(right, weight=1)

        self._build_controls(left)
        self._build_outputs(right)

    def _make_entry(self, parent: ttk.Frame, label: str, key: str, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        variable = tk.StringVar()
        self.variables[key] = variable
        ttk.Entry(parent, textvariable=variable, width=18).grid(
            row=row,
            column=1,
            sticky="ew",
            padx=(8, 0),
            pady=3,
        )

    def _build_controls(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        metadata = ttk.LabelFrame(parent, text="Experiment Context", padding=10)
        metadata.grid(row=0, column=0, sticky="ew")
        metadata.columnconfigure(1, weight=1)
        ttk.Label(metadata, text="Atomic species").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(metadata, text="87Rb").grid(row=0, column=1, sticky="w", pady=2)
        ttk.Label(metadata, text="Bragg order").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(metadata, text="1st order").grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(metadata, text="Sequence").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Label(metadata, text="pi/2 - pi - pi/2").grid(row=2, column=1, sticky="w", pady=2)
        ttk.Label(
            metadata,
            text="Noise model: shot-to-shot Gaussian noise on the selected distribution center detuning.",
            wraplength=360,
            justify=tk.LEFT,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        pulse_frame = ttk.LabelFrame(parent, text="Pulse Model", padding=10)
        pulse_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        pulse_frame.columnconfigure(1, weight=1)
        self._make_entry(pulse_frame, "Beam splitter duration (us)", "bs_duration_us", 0)
        self._make_entry(pulse_frame, "Mirror duration (us)", "mirror_duration_us", 1)
        self._make_entry(pulse_frame, "Dark time T (ms)", "dark_time_ms", 2)
        self._make_entry(pulse_frame, "Pulse truncation (sigma)", "truncate_sigma", 3)
        self._make_entry(pulse_frame, "Pulse time steps", "time_steps", 4)

        ttk.Label(pulse_frame, text="Duration convention").grid(row=5, column=0, sticky="w", pady=3)
        duration_var = tk.StringVar()
        self.variables["duration_convention"] = duration_var
        duration_box = ttk.Combobox(
            pulse_frame,
            textvariable=duration_var,
            state="readonly",
            values=[mode.value for mode in DurationConvention],
            width=24,
        )
        duration_box.grid(row=5, column=1, sticky="ew", padx=(8, 0), pady=3)

        ensemble_frame = ttk.LabelFrame(parent, text="Velocity Ensemble", padding=10)
        ensemble_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ensemble_frame.columnconfigure(1, weight=1)
        self._make_entry(
            ensemble_frame,
            "Distribution FWHM (kHz)",
            "distribution_fwhm_khz",
            0,
        )
        self._make_entry(
            ensemble_frame,
            "Nominal mean detuning (kHz)",
            "nominal_center_khz",
            1,
        )
        self._make_entry(
            ensemble_frame,
            "Shot noise RMS (kHz)",
            "shot_noise_sigma_khz",
            2,
        )

        analysis_frame = ttk.LabelFrame(parent, text="Analysis Sampling", padding=10)
        analysis_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        analysis_frame.columnconfigure(1, weight=1)
        self._make_entry(
            analysis_frame,
            "Center scan half-width (kHz)",
            "center_scan_halfwidth_khz",
            0,
        )
        self._make_entry(analysis_frame, "Center scan points", "center_scan_points", 1)
        self._make_entry(analysis_frame, "Noise sweep max RMS (kHz)", "noise_sweep_max_khz", 2)
        self._make_entry(analysis_frame, "Noise sweep points", "noise_sweep_points", 3)
        self._make_entry(analysis_frame, "Gauss-Hermite points", "gauss_hermite_points", 4)
        self._make_entry(analysis_frame, "Detuning grid points", "detuning_grid_points", 5)
        self._make_entry(analysis_frame, "Monte Carlo shots", "monte_carlo_shots", 6)
        self._make_entry(analysis_frame, "Random seed", "random_seed", 7)

        button_frame = ttk.Frame(parent, padding=(0, 12, 0, 0))
        button_frame.grid(row=4, column=0, sticky="ew")
        ttk.Button(button_frame, text="Run Model", command=self.run_model).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )
        ttk.Button(button_frame, text="Save Figure", command=self.save_figure).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )
        ttk.Button(button_frame, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(
            parent,
            textvariable=self.status_var,
            wraplength=380,
            justify=tk.LEFT,
        ).grid(row=5, column=0, sticky="ew", pady=(14, 0))

    def _build_outputs(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        self.summary_text = tk.Text(parent, height=13, wrap=tk.WORD)
        self.summary_text.grid(row=0, column=0, sticky="ew")

        figure_frame = ttk.Frame(parent)
        figure_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        figure_frame.rowconfigure(0, weight=1)
        figure_frame.columnconfigure(0, weight=1)

        self.figure = Figure(figsize=(11.5, 8.0), dpi=110, constrained_layout=True)
        self.axes = self.figure.subplots(2, 2)
        self.canvas = FigureCanvasTkAgg(self.figure, master=figure_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        toolbar = NavigationToolbar2Tk(self.canvas, figure_frame, pack_toolbar=False)
        toolbar.update()
        toolbar.grid(row=1, column=0, sticky="ew")

    def _set_default_values(self) -> None:
        defaults = {
            "bs_duration_us": "25",
            "mirror_duration_us": "50",
            "dark_time_ms": "8",
            "truncate_sigma": "4.5",
            "time_steps": "320",
            "distribution_fwhm_khz": "12",
            "nominal_center_khz": "0",
            "shot_noise_sigma_khz": "4",
            "center_scan_halfwidth_khz": "12",
            "center_scan_points": "241",
            "noise_sweep_max_khz": "8",
            "noise_sweep_points": "31",
            "gauss_hermite_points": "41",
            "detuning_grid_points": "401",
            "monte_carlo_shots": "256",
            "random_seed": "12345",
            "duration_convention": DurationConvention.SIGMA.value,
        }
        for key, value in defaults.items():
            self.variables[key].set(value)

    def _parse_inputs(self) -> tuple[InterferometerConfig, EnsembleConfig, AnalysisConfig]:
        try:
            duration_convention = DurationConvention(self.variables["duration_convention"].get())
            interferometer = InterferometerConfig(
                beamsplitter=PulseSpec(duration_us=float(self.variables["bs_duration_us"].get()), target_area_rad=np.pi / 2.0),
                mirror=PulseSpec(duration_us=float(self.variables["mirror_duration_us"].get()), target_area_rad=np.pi),
                dark_time_ms=float(self.variables["dark_time_ms"].get()),
                duration_convention=duration_convention,
                truncate_sigma=float(self.variables["truncate_sigma"].get()),
                time_steps=int(self.variables["time_steps"].get()),
            )
            ensemble = EnsembleConfig(
                distribution_fwhm_khz=float(self.variables["distribution_fwhm_khz"].get()),
                nominal_center_khz=float(self.variables["nominal_center_khz"].get()),
                shot_noise_sigma_khz=float(self.variables["shot_noise_sigma_khz"].get()),
            )
            analysis = AnalysisConfig(
                center_scan_halfwidth_khz=float(self.variables["center_scan_halfwidth_khz"].get()),
                center_scan_points=int(self.variables["center_scan_points"].get()),
                noise_sweep_max_khz=float(self.variables["noise_sweep_max_khz"].get()),
                noise_sweep_points=int(self.variables["noise_sweep_points"].get()),
                monte_carlo_shots=int(self.variables["monte_carlo_shots"].get()),
                gauss_hermite_points=int(self.variables["gauss_hermite_points"].get()),
                detuning_grid_points=int(self.variables["detuning_grid_points"].get()),
                random_seed=int(self.variables["random_seed"].get()),
            )
        except ValueError as error:
            raise ValueError(f"Input parsing failed: {error}") from error

        if interferometer.beamsplitter.duration_us <= 0.0 or interferometer.mirror.duration_us <= 0.0:
            raise ValueError("Pulse durations must be positive.")
        if interferometer.dark_time_ms < 0.0:
            raise ValueError("Dark time must be non-negative.")
        if ensemble.distribution_fwhm_khz <= 0.0:
            raise ValueError("Distribution FWHM must be positive.")
        if ensemble.shot_noise_sigma_khz < 0.0:
            raise ValueError("Shot noise RMS must be non-negative.")
        if analysis.center_scan_points < 5 or analysis.noise_sweep_points < 2:
            raise ValueError("Sweep point counts are too small.")
        if analysis.gauss_hermite_points < 8:
            raise ValueError("Use at least 8 Gauss-Hermite points.")
        if analysis.detuning_grid_points < 80:
            raise ValueError("Use at least 80 detuning grid points.")
        if interferometer.time_steps < 40:
            raise ValueError("Use at least 40 pulse time steps.")
        return interferometer, ensemble, analysis

    def _update_summary(
        self,
        interferometer: InterferometerConfig,
        ensemble: EnsembleConfig,
        outputs: ModelOutputs,
    ) -> None:
        shot_noise = ensemble.shot_noise_sigma_khz
        total_sigma_linear = np.interp(
            shot_noise,
            outputs.noise_sweep_khz,
            outputs.total_sigma_phi_linear_rad,
        )
        total_sigma_mc = np.interp(
            shot_noise,
            outputs.noise_sweep_khz,
            outputs.total_sigma_phi_monte_carlo_rad,
        )
        diff_sigma_linear = np.interp(
            shot_noise,
            outputs.noise_sweep_khz,
            outputs.diffraction_sigma_phi_linear_rad,
            )
        diff_sigma_mc = np.interp(
            shot_noise,
            outputs.noise_sweep_khz,
            outputs.diffraction_sigma_phi_monte_carlo_rad,
        )

        distribution_sigma_khz = fwhm_to_sigma(ensemble.distribution_fwhm_khz)
        lines = [
            "Model summary",
            "",
            "Physics model: ensemble-averaged two-level finite-duration Bragg solver.",
            "Pulse-only diffraction phase: three-pulse sequence with dark-time phase accumulation suppressed.",
            f"Atomic species: 87Rb | Bragg order: 1 | T = {interferometer.dark_time_ms:.3f} ms",
            f"Selected distribution: Gaussian, FWHM = {ensemble.distribution_fwhm_khz:.3f} kHz, sigma = {distribution_sigma_khz:.3f} kHz",
            f"Nominal center detuning: {ensemble.nominal_center_khz:.3f} kHz",
            f"Shot-to-shot center noise RMS: {shot_noise:.3f} kHz",
            "",
            f"Nominal total fringe phase: {rad_to_mrad(outputs.nominal_total_phase_rad):.3f} mrad",
            f"Nominal pulse-only diffraction phase: {rad_to_mrad(outputs.nominal_diffraction_phase_rad):.3f} mrad",
            f"Nominal total contrast: {outputs.nominal_total_contrast:.4f}",
            f"Nominal pulse-only contrast: {outputs.nominal_diffraction_contrast:.4f}",
            "",
            f"d(phi_total)/d(center detuning): {rad_to_mrad(outputs.total_phase_slope_rad_per_khz):.3f} mrad/kHz",
            f"d(phi_diff)/d(center detuning): {rad_to_mrad(outputs.diffraction_phase_slope_rad_per_khz):.3f} mrad/kHz",
            "",
            f"At sigma_noise = {shot_noise:.3f} kHz:",
            f"Linear sigma_phi,total = {rad_to_mrad(total_sigma_linear):.3f} mrad",
            f"Monte Carlo sigma_phi,total = {rad_to_mrad(total_sigma_mc):.3f} mrad",
            f"Linear sigma_phi,diffraction = {rad_to_mrad(diff_sigma_linear):.3f} mrad",
            f"Monte Carlo sigma_phi,diffraction = {rad_to_mrad(diff_sigma_mc):.3f} mrad",
        ]
        self.summary_text.delete("1.0", tk.END)
        self.summary_text.insert("1.0", "\n".join(lines))

    def _update_plots(
        self,
        ensemble: EnsembleConfig,
        outputs: ModelOutputs,
    ) -> None:
        for axis in self.axes.flat:
            axis.clear()

        nominal_index = int(np.argmin(np.abs(outputs.center_scan_khz - ensemble.nominal_center_khz)))
        total_phase_scan = unwrap_series(outputs.total_phase_scan_rad)
        diff_phase_scan = unwrap_series(outputs.diffraction_phase_scan_rad)
        total_phase_change = rad_to_mrad(total_phase_scan - total_phase_scan[nominal_index])
        diff_phase_change = rad_to_mrad(diff_phase_scan - diff_phase_scan[nominal_index])

        dist_axis = self.axes[0, 0]
        sigma_khz = fwhm_to_sigma(ensemble.distribution_fwhm_khz)
        x_distribution = np.linspace(
            ensemble.nominal_center_khz - 4.0 * sigma_khz,
            ensemble.nominal_center_khz + 4.0 * sigma_khz,
            500,
        )
        nominal_profile = np.exp(-0.5 * np.square((x_distribution - ensemble.nominal_center_khz) / sigma_khz))
        noisy_profile = np.exp(-0.5 * np.square((x_distribution - (ensemble.nominal_center_khz + ensemble.shot_noise_sigma_khz)) / sigma_khz))
        dist_axis.plot(x_distribution, nominal_profile, label="Nominal shot")
        dist_axis.plot(x_distribution, noisy_profile, linestyle="--", label="+1 RMS center shift")
        dist_axis.set_title("Selected Velocity Distribution")
        dist_axis.set_xlabel("Center detuning relative to Bragg resonance (kHz)")
        dist_axis.set_ylabel("Arbitrary density")
        dist_axis.legend()

        phase_axis = self.axes[0, 1]
        phase_axis.plot(outputs.center_scan_khz, total_phase_change, label="Total fringe phase")
        phase_axis.plot(outputs.center_scan_khz, diff_phase_change, label="Pulse-only diffraction phase")
        phase_axis.axvline(ensemble.nominal_center_khz, color="black", alpha=0.3, linewidth=1.0)
        phase_axis.set_title("Phase Change vs. Distribution Center")
        phase_axis.set_xlabel("Shot center detuning (kHz)")
        phase_axis.set_ylabel("Phase change (mrad)")
        phase_axis.legend()

        noise_axis = self.axes[1, 0]
        noise_axis.plot(
            outputs.noise_sweep_khz,
            rad_to_mrad(outputs.total_sigma_phi_linear_rad),
            label="Total phase (linearized)",
        )
        noise_axis.plot(
            outputs.noise_sweep_khz,
            rad_to_mrad(outputs.total_sigma_phi_monte_carlo_rad),
            linestyle="--",
            label="Total phase (Monte Carlo)",
        )
        noise_axis.plot(
            outputs.noise_sweep_khz,
            rad_to_mrad(outputs.diffraction_sigma_phi_linear_rad),
            label="Diffraction phase (linearized)",
        )
        noise_axis.plot(
            outputs.noise_sweep_khz,
            rad_to_mrad(outputs.diffraction_sigma_phi_monte_carlo_rad),
            linestyle="--",
            label="Diffraction phase (Monte Carlo)",
        )
        noise_axis.axvline(ensemble.shot_noise_sigma_khz, color="black", alpha=0.3, linewidth=1.0)
        noise_axis.set_title("Phase Noise vs. Raman Center-Noise RMS")
        noise_axis.set_xlabel("Center-noise RMS (kHz)")
        noise_axis.set_ylabel("sigma_phi (mrad)")
        noise_axis.legend()

        contrast_axis = self.axes[1, 1]
        contrast_axis.plot(outputs.center_scan_khz, outputs.total_contrast_scan, label="Total sequence")
        contrast_axis.plot(outputs.center_scan_khz, outputs.diffraction_contrast_scan, label="Pulse-only sequence")
        contrast_axis.axvline(ensemble.nominal_center_khz, color="black", alpha=0.3, linewidth=1.0)
        contrast_axis.set_title("Fringe Contrast vs. Distribution Center")
        contrast_axis.set_xlabel("Shot center detuning (kHz)")
        contrast_axis.set_ylabel("Contrast")
        contrast_axis.legend()

        self.figure.suptitle("Bragg Phase Noise from Raman Velocity-Selection Noise")
        self.canvas.draw_idle()

    def run_model(self) -> None:
        try:
            interferometer, ensemble, analysis = self._parse_inputs()
        except ValueError as error:
            messagebox.showerror("Input Error", str(error))
            return

        self.status_var.set("Running finite-duration Bragg solver...")
        self.update_idletasks()
        try:
            model = BraggPhaseNoiseModel(
                interferometer=interferometer,
                ensemble=ensemble,
                analysis=analysis,
            )
            outputs = model.run()
        except Exception as error:  # pragma: no cover - UI safety net.
            messagebox.showerror("Computation Error", str(error))
            self.status_var.set("Computation failed.")
            return

        self.current_outputs = outputs
        self._update_summary(interferometer, ensemble, outputs)
        self._update_plots(ensemble, outputs)
        self.status_var.set("Model run completed.")

    def save_figure(self) -> None:
        if self.current_outputs is None:
            messagebox.showinfo("No Figure", "Run the model before saving a figure.")
            return
        target = filedialog.asksaveasfilename(
            title="Save figure",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("PDF file", "*.pdf"), ("SVG file", "*.svg")],
        )
        if not target:
            return
        self.figure.savefig(target, dpi=300, bbox_inches="tight")
        self.status_var.set(f"Figure saved to {target}")

    def export_csv(self) -> None:
        if self.current_outputs is None:
            messagebox.showinfo("No Data", "Run the model before exporting data.")
            return

        target = filedialog.asksaveasfilename(
            title="Choose export base name",
            defaultextension=".csv",
            filetypes=[("CSV file", "*.csv")],
        )
        if not target:
            return

        base = Path(target)
        if base.suffix.lower() == ".csv":
            base = base.with_suffix("")

        center_path = base.parent / f"{base.name}_center_scan.csv"
        noise_path = base.parent / f"{base.name}_noise_sweep.csv"

        with center_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "center_detuning_khz",
                    "total_phase_rad",
                    "diffraction_phase_rad",
                    "total_contrast",
                    "diffraction_contrast",
                ]
            )
            for row in zip(
                self.current_outputs.center_scan_khz,
                self.current_outputs.total_phase_scan_rad,
                self.current_outputs.diffraction_phase_scan_rad,
                self.current_outputs.total_contrast_scan,
                self.current_outputs.diffraction_contrast_scan,
            ):
                writer.writerow(row)

        with noise_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "noise_sigma_khz",
                    "total_sigma_phi_linear_rad",
                    "total_sigma_phi_monte_carlo_rad",
                    "diffraction_sigma_phi_linear_rad",
                    "diffraction_sigma_phi_monte_carlo_rad",
                ]
            )
            for row in zip(
                self.current_outputs.noise_sweep_khz,
                self.current_outputs.total_sigma_phi_linear_rad,
                self.current_outputs.total_sigma_phi_monte_carlo_rad,
                self.current_outputs.diffraction_sigma_phi_linear_rad,
                self.current_outputs.diffraction_sigma_phi_monte_carlo_rad,
            ):
                writer.writerow(row)

        self.status_var.set(f"CSV exported to {center_path.name} and {noise_path.name}")


def launch_app() -> None:
    app = Application()
    app.mainloop()
