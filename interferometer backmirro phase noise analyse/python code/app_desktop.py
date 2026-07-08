
from __future__ import annotations

import math
import re
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib
matplotlib.use("TkAgg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


@dataclass
class ModelParameters:
    wavelength_m: float = 780e-9
    interrogation_time_s: float = 0.4
    cycle_time_s: float = 1.0
    reflection_factor: float = 4.0
    cycle_response_prefactor: float = 2.0


def parse_numeric_series(series: pd.Series) -> pd.Series:
    """Robust parsing for decimal commas, units, and scientific notation."""
    def parse_one(value):
        if pd.isna(value):
            return np.nan

        if isinstance(value, (int, float, np.number)):
            return float(value)

        text = str(value).strip()
        if not text:
            return np.nan

        text = text.replace("\u00a0", "").replace(" ", "")
        text = text.replace("D", "E").replace("d", "e")

        if "," in text and "." not in text:
            if text.count(",") == 1:
                text = text.replace(",", ".")
            else:
                text = text.replace(",", "")
        elif "," in text and "." in text:
            text = text.replace(",", "")

        match = re.search(
            r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?",
            text,
        )
        if not match:
            return np.nan

        try:
            return float(match.group(0))
        except ValueError:
            return np.nan

    return series.map(parse_one).astype(float)


def sensitivity_function(omega: np.ndarray, T: float) -> np.ndarray:
    return 8.0 * np.sin(omega * T / 2.0) * np.sin(omega * T / 4.0) ** 2


def cycle_response_squared(
    omega: np.ndarray,
    Tc: float,
    prefactor: float,
) -> np.ndarray:
    return prefactor * np.sin(omega * Tc / 2.0) ** 2


def integrate_trapezoid(y: np.ndarray, x: np.ndarray) -> float:
    """NumPy-version-compatible trapezoidal integration."""
    if hasattr(np, "trapezoid"):
        return float(np.trapezoid(y, x))
    return float(np.trapz(y, x))


class SeismicAtomPhaseApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Seismic-Induced Atom Phase Noise")
        self.root.geometry("1450x900")
        self.root.minsize(1100, 720)

        self.file_path: Path | None = None
        self.excel_file: pd.ExcelFile | None = None
        self.raw_df: pd.DataFrame | None = None
        self.result_df: pd.DataFrame | None = None

        self.file_var = tk.StringVar(value="No file selected")
        self.sheet_var = tk.StringVar()
        self.freq_col_var = tk.StringVar()
        self.acc_col_var = tk.StringVar()

        self.lambda_var = tk.StringVar(value="780")
        self.T_var = tk.StringVar(value="0.4")
        self.Tc_var = tk.StringVar(value="1.0")
        self.R_var = tk.StringVar(value="4.0")
        self.C_var = tk.StringVar(value="2.0")
        self.fmin_var = tk.StringVar(value="")
        self.fmax_var = tk.StringVar(value="")
        self.rms_var = tk.StringVar(value="RMS: --")

        self._build_ui()

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        control = ttk.LabelFrame(main, text="Data and Parameters", padding=10)
        control.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        plot_frame = ttk.Frame(main)
        plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        row = 0
        ttk.Button(control, text="Select Excel File", command=self.open_file).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(0, 6)
        )
        row += 1

        file_label = ttk.Label(
            control,
            textvariable=self.file_var,
            wraplength=280,
            justify=tk.LEFT,
        )
        file_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
        row += 1

        ttk.Label(control, text="Worksheet").grid(row=row, column=0, sticky="w")
        self.sheet_combo = ttk.Combobox(
            control,
            textvariable=self.sheet_var,
            state="readonly",
            width=28,
        )
        self.sheet_combo.grid(row=row, column=1, sticky="ew", pady=2)
        self.sheet_combo.bind("<<ComboboxSelected>>", self.on_sheet_changed)
        row += 1

        ttk.Label(control, text="Frequency Column").grid(row=row, column=0, sticky="w")
        self.freq_combo = ttk.Combobox(
            control,
            textvariable=self.freq_col_var,
            state="readonly",
            width=28,
        )
        self.freq_combo.grid(row=row, column=1, sticky="ew", pady=2)
        self.freq_combo.bind("<<ComboboxSelected>>", self.on_frequency_changed)
        row += 1

        ttk.Label(control, text="Acceleration ASD Column").grid(row=row, column=0, sticky="w")
        self.acc_combo = ttk.Combobox(
            control,
            textvariable=self.acc_col_var,
            state="readonly",
            width=28,
        )
        self.acc_combo.grid(row=row, column=1, sticky="ew", pady=2)
        row += 1

        ttk.Separator(control).grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1

        entries = [
            ("Laser wavelength λ (nm)", self.lambda_var),
            ("Interrogation time T (s)", self.T_var),
            ("Cycle time Tc (s)", self.Tc_var),
            ("Phase coefficient R", self.R_var),
            ("Cycle-response coefficient C", self.C_var),
            ("Integration lower bound fmin (Hz)", self.fmin_var),
            ("Integration upper bound fmax (Hz)", self.fmax_var),
        ]

        for label, var in entries:
            ttk.Label(control, text=label).grid(row=row, column=0, sticky="w")
            ttk.Entry(control, textvariable=var, width=18).grid(
                row=row, column=1, sticky="ew", pady=2
            )
            row += 1

        ttk.Separator(control).grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1

        ttk.Button(control, text="Compute and Plot", command=self.calculate).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=4
        )
        row += 1

        ttk.Button(control, text="Export Results CSV", command=self.export_csv).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=4
        )
        row += 1

        ttk.Button(control, text="Save All Figures", command=self.save_figures).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=4
        )
        row += 1

        ttk.Label(
            control,
            textvariable=self.rms_var,
            font=("TkDefaultFont", 11, "bold"),
            wraplength=280,
            justify=tk.LEFT,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(12, 4))
        row += 1

        self.status_text = tk.Text(control, width=36, height=14, wrap=tk.WORD)
        self.status_text.grid(row=row, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        control.rowconfigure(row, weight=1)
        control.columnconfigure(1, weight=1)

        self.notebook = ttk.Notebook(plot_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.plot_tabs = {}
        for key, title in [
            ("acc", "Acceleration ASD"),
            ("laser", "Laser Phase ASD"),
            ("atom", "Atom Phase PSD"),
            ("rms", "Cumulative RMS"),
        ]:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=title)

            fig = Figure(figsize=(8, 6), dpi=100)
            ax = fig.add_subplot(111)
            ax.set_title(title)
            ax.grid(True, which="both", alpha=0.25)

            canvas = FigureCanvasTkAgg(fig, master=frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            toolbar = NavigationToolbar2Tk(canvas, frame)
            toolbar.update()

            self.plot_tabs[key] = (fig, ax, canvas)

    def clear_log(self):
        self.status_text.delete("1.0", tk.END)

    def log(self, message: str):
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.root.update_idletasks()

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Select Acceleration ASD Excel File",
            filetypes=[
                ("Excel files", "*.xls *.xlsx"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        try:
            self.clear_log()
            self.file_path = Path(path)
            engine = "xlrd" if self.file_path.suffix.lower() == ".xls" else "openpyxl"
            self.excel_file = pd.ExcelFile(self.file_path, engine=engine)

            self.file_var.set(str(self.file_path))
            self.sheet_combo["values"] = self.excel_file.sheet_names

            preferred = "Sheet1" if "Sheet1" in self.excel_file.sheet_names else self.excel_file.sheet_names[0]
            self.sheet_var.set(preferred)

            self.load_sheet(preferred)
            self.log(f"Loaded file: {self.file_path.name}")
            self.log(f"Worksheets: {', '.join(self.excel_file.sheet_names)}")

        except Exception as exc:
            messagebox.showerror("Load Failed", str(exc))

    def load_sheet(self, sheet_name: str):
        if self.excel_file is None:
            return

        self.raw_df = pd.read_excel(
            self.excel_file,
            sheet_name=sheet_name,
            dtype=object,
        )

        columns = [str(c) for c in self.raw_df.columns]
        self.raw_df.columns = columns

        self.freq_combo["values"] = columns

        freq_default = columns[0]
        for col in columns:
            col_lower = col.lower()
            if "freq" in col_lower or "hz" in col_lower or "频率" in col:
                freq_default = col
                break

        self.freq_col_var.set(freq_default)
        self.update_acceleration_columns()

        self.log(f"Loaded worksheet {sheet_name}: {len(self.raw_df)} rows, {len(columns)} columns")
        self.log("Column names:")
        for col in columns:
            self.log(f"  - {col}")

    def on_sheet_changed(self, _event=None):
        selected = self.sheet_var.get()
        if selected:
            self.load_sheet(selected)

    def on_frequency_changed(self, _event=None):
        self.update_acceleration_columns()

    def update_acceleration_columns(self):
        if self.raw_df is None:
            return

        freq_col = self.freq_col_var.get()
        candidates = [c for c in self.raw_df.columns if c != freq_col]
        self.acc_combo["values"] = candidates

        if candidates:
            self.acc_col_var.set(candidates[0])

    def get_parameters(self) -> ModelParameters:
        try:
            wavelength_nm = float(self.lambda_var.get())
            T = float(self.T_var.get())
            Tc = float(self.Tc_var.get())
            R = float(self.R_var.get())
            C = float(self.C_var.get())
        except ValueError as exc:
            raise ValueError("Physical parameters must be valid numbers.") from exc

        if wavelength_nm <= 0:
            raise ValueError("Laser wavelength must be greater than 0.")
        if T < 0 or Tc < 0:
            raise ValueError("T and Tc must be non-negative.")
        if R < 0 or C < 0:
            raise ValueError("R and C must be non-negative.")

        return ModelParameters(
            wavelength_m=wavelength_nm * 1e-9,
            interrogation_time_s=T,
            cycle_time_s=Tc,
            reflection_factor=R,
            cycle_response_prefactor=C,
        )

    def clean_data(self) -> pd.DataFrame:
        if self.raw_df is None:
            raise ValueError("Please select an Excel file first.")

        freq_col = self.freq_col_var.get()
        acc_col = self.acc_col_var.get()

        if not freq_col or not acc_col:
            raise ValueError("Please select both a frequency column and an acceleration ASD column.")

        freq = parse_numeric_series(self.raw_df[freq_col])
        acc = parse_numeric_series(self.raw_df[acc_col])

        data = pd.DataFrame({
            "frequency_hz": freq,
            "acceleration_asd": acc,
        })

        before = len(data)
        data = data.replace([np.inf, -np.inf], np.nan).dropna()
        finite = len(data)

        data = data[
            (data["frequency_hz"] > 0)
            & (data["acceleration_asd"] >= 0)
        ]
        positive = len(data)

        data = data.sort_values("frequency_hz")
        data = data.drop_duplicates("frequency_hz").reset_index(drop=True)

        self.log(
            f"Data cleaning: {before} raw rows; {finite} finite numeric rows; "
            f"{positive} rows with positive frequency and non-negative ASD; {len(data)} final rows."
        )

        if len(data) < 2:
            raise ValueError("Fewer than 2 valid data points remain. Check the selected columns and data format.")

        return data

    def calculate(self):
        try:
            data = self.clean_data()
            params = self.get_parameters()

            f = data["frequency_hz"].to_numpy(dtype=float)
            a_asd = data["acceleration_asd"].to_numpy(dtype=float)
            omega = 2.0 * np.pi * f

            x_asd = a_asd / omega**2
            laser_phase_asd = (
                params.reflection_factor * np.pi / params.wavelength_m
            ) * x_asd

            H_ai = sensitivity_function(omega, params.interrogation_time_s)
            H_diff_sq = cycle_response_squared(
                omega,
                params.cycle_time_s,
                params.cycle_response_prefactor,
            )

            atom_phase_psd = H_diff_sq * H_ai**2 * laser_phase_asd**2
            atom_phase_asd = np.sqrt(np.maximum(atom_phase_psd, 0.0))

            segment_area = 0.5 * (
                atom_phase_psd[1:] + atom_phase_psd[:-1]
            ) * np.diff(f)
            cumulative_variance = np.concatenate([[0.0], np.cumsum(segment_area)])
            cumulative_rms = np.sqrt(np.maximum(cumulative_variance, 0.0))

            self.result_df = data.copy()
            self.result_df["omega_rad_s"] = omega
            self.result_df["displacement_asd_m_sqrtHz"] = x_asd
            self.result_df["laser_phase_asd_rad_sqrtHz"] = laser_phase_asd
            self.result_df["H_AI"] = H_ai
            self.result_df["H_diff_squared"] = H_diff_sq
            self.result_df["atom_phase_psd_rad2_Hz"] = atom_phase_psd
            self.result_df["atom_phase_asd_rad_sqrtHz"] = atom_phase_asd
            self.result_df["cumulative_rms_rad"] = cumulative_rms

            data_min = float(f.min())
            data_max = float(f.max())

            fmin = data_min if not self.fmin_var.get().strip() else float(self.fmin_var.get())
            fmax = data_max if not self.fmax_var.get().strip() else float(self.fmax_var.get())

            if fmin >= fmax:
                raise ValueError("The integration lower bound must be smaller than the upper bound.")

            mask = (f >= fmin) & (f <= fmax)
            if np.count_nonzero(mask) < 2:
                raise ValueError("Fewer than 2 valid points exist inside the requested integration band.")

            variance = integrate_trapezoid(atom_phase_psd[mask], f[mask])
            variance = max(float(variance), 0.0)
            rms = math.sqrt(variance)

            self.rms_var.set(
                f"RMS = {rms:.6e} rad\n"
                f"Variance = {variance:.6e} rad²\n"
                f"Band = {fmin:.6g} – {fmax:.6g} Hz"
            )

            if not self.fmin_var.get().strip():
                self.fmin_var.set(f"{data_min:.8g}")
            if not self.fmax_var.get().strip():
                self.fmax_var.set(f"{data_max:.8g}")

            self.update_plots()
            self.log(f"Computation complete: RMS = {rms:.6e} rad")

        except Exception as exc:
            messagebox.showerror("Computation Failed", str(exc))

    def _plot_log(self, key: str, x, y, title, ylabel, label):
        fig, ax, canvas = self.plot_tabs[key]
        ax.clear()

        valid = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
        ax.loglog(x[valid], y[valid], label=label)
        ax.set_title(title)
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel(ylabel)
        ax.grid(True, which="major", alpha=0.35)
        ax.grid(True, which="minor", alpha=0.15)
        ax.legend()
        fig.tight_layout()
        canvas.draw()

    def update_plots(self):
        if self.result_df is None:
            return

        f = self.result_df["frequency_hz"].to_numpy()

        self._plot_log(
            "acc",
            f,
            self.result_df["acceleration_asd"].to_numpy(),
            "Measured acceleration ASD",
            r"Acceleration ASD (m s$^{-2}$ Hz$^{-1/2}$)",
            self.acc_col_var.get(),
        )

        self._plot_log(
            "laser",
            f,
            self.result_df["laser_phase_asd_rad_sqrtHz"].to_numpy(),
            "Laser phase ASD induced by seismic motion",
            r"Laser phase ASD (rad Hz$^{-1/2}$)",
            "Laser phase ASD",
        )

        self._plot_log(
            "atom",
            f,
            self.result_df["atom_phase_psd_rad2_Hz"].to_numpy(),
            "Atom phase PSD after sensitivity functions",
            r"Atom phase PSD (rad$^2$ Hz$^{-1}$)",
            "Atom phase PSD",
        )

        self._plot_log(
            "rms",
            f,
            self.result_df["cumulative_rms_rad"].to_numpy(),
            "Cumulative atom phase RMS",
            "Cumulative RMS (rad)",
            "Cumulative RMS",
        )

    def export_csv(self):
        if self.result_df is None:
            messagebox.showwarning("No Results", "Please run the calculation first.")
            return

        path = filedialog.asksaveasfilename(
            title="Save Computation Results",
            defaultextension=".csv",
            filetypes=[("CSV file", "*.csv")],
            initialfile="seismic_atom_phase_results.csv",
        )
        if not path:
            return

        self.result_df.to_csv(path, index=False, encoding="utf-8-sig")
        messagebox.showinfo("Save Complete", f"Results saved to:\n{path}")

    def save_figures(self):
        if self.result_df is None:
            messagebox.showwarning("No Results", "Please run the calculation first.")
            return

        directory = filedialog.askdirectory(title="Select Figure Output Directory")
        if not directory:
            return

        directory = Path(directory)
        for key, filename in [
            ("acc", "acceleration_asd.png"),
            ("laser", "laser_phase_asd.png"),
            ("atom", "atom_phase_psd.png"),
            ("rms", "cumulative_rms.png"),
        ]:
            fig, _, _ = self.plot_tabs[key]
            fig.savefig(directory / filename, dpi=300, bbox_inches="tight")

        messagebox.showinfo("Save Complete", f"Figures saved to:\n{directory}")


def main():
    root = tk.Tk()
    app = SeismicAtomPhaseApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
