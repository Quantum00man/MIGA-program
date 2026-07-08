from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

try:
    import allantools
except ImportError:
    allantools = None


APP_TITLE = "Allan Variance Analyzer"
DEFAULT_TAUS = "octave"
INSTALL_HINT = "python3 -m pip install -r requirements.txt"
SCALE_LABELS = {"Linear": "linear", "Log": "log"}
OVERLAP_LABELS = {
    "overlapping": "Overlapping",
    "non_overlapping": "Non-overlapping",
}
NORMALIZATION_LABELS = {
    "absolute": "Absolute",
    "relative": "Relative",
}
DISPLAY_MODE_LABELS = {
    "deviation": "Allan Deviation",
    "variance": "Allan Variance",
}


@dataclass
class AllanAnalysisResult:
    taus: np.ndarray
    adev: np.ndarray
    avar: np.ndarray
    mean_value: float
    sample_count: int
    skipped_rows: int
    sampling_interval: float
    sample_rate: float
    column_index: int
    overlap_mode: str
    variance_mode: str
    dropped_points: int = 0


def load_numeric_csv_column(path: str | Path, column_index: int) -> tuple[np.ndarray, int]:
    if column_index < 1:
        raise ValueError("Column index must start at 1.")

    csv_path = Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"File not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel

        reader = csv.reader(handle, dialect)
        values: list[float] = []
        skipped_rows = 0

        for row in reader:
            if not row or all(not cell.strip() for cell in row):
                continue
            if len(row) < column_index:
                skipped_rows += 1
                continue

            cell = row[column_index - 1].strip()
            if not cell:
                skipped_rows += 1
                continue

            try:
                values.append(float(cell))
            except ValueError:
                skipped_rows += 1

    if not values:
        raise ValueError("No numeric values were found in the selected column.")

    return np.asarray(values, dtype=float), skipped_rows


def prepare_frequency_series(data: np.ndarray, variance_mode: str) -> tuple[np.ndarray, float]:
    mean_value = float(np.mean(data))

    if variance_mode == "relative":
        if np.isclose(mean_value, 0.0):
            raise ValueError("Relative mode requires a mean value that is not close to zero.")
        return data / mean_value, mean_value

    return np.array(data, copy=True), mean_value


def compute_allan_variance(
    data: np.ndarray,
    sampling_interval: float,
    overlap_mode: str,
    variance_mode: str,
    column_index: int,
    skipped_rows: int,
) -> AllanAnalysisResult:
    if allantools is None:
        raise RuntimeError(
            "The allantools package is not installed.\nPlease run:\n"
            f"{INSTALL_HINT}"
        )

    if sampling_interval <= 0:
        raise ValueError("Sampling interval t must be greater than 0.")
    if data.size < 3:
        raise ValueError("At least 3 samples are required to compute Allan variance.")

    series, mean_value = prepare_frequency_series(data, variance_mode)
    sample_rate = 1.0 / sampling_interval
    compute_fn = allantools.oadev if overlap_mode == "overlapping" else allantools.adev

    taus, adev, _, _ = compute_fn(
        series,
        rate=sample_rate,
        data_type="freq",
        taus=DEFAULT_TAUS,
    )

    taus = np.asarray(taus)
    adev = np.asarray(adev)
    avar = np.square(adev)
    mask = np.isfinite(taus) & np.isfinite(adev) & np.isfinite(avar)
    taus = taus[mask]
    adev = adev[mask]
    avar = avar[mask]

    if taus.size == 0 or avar.size == 0:
        raise ValueError("No valid Allan result was produced. Check the data length and sampling interval.")

    return AllanAnalysisResult(
        taus=taus,
        adev=adev,
        avar=avar,
        mean_value=mean_value,
        sample_count=int(data.size),
        skipped_rows=skipped_rows,
        sampling_interval=sampling_interval,
        sample_rate=sample_rate,
        column_index=column_index,
        overlap_mode=overlap_mode,
        variance_mode=variance_mode,
    )


def filter_points_for_scale(
    taus: np.ndarray,
    y_values: np.ndarray,
    xscale: str,
    yscale: str,
) -> tuple[np.ndarray, np.ndarray, int]:
    mask = np.isfinite(taus) & np.isfinite(y_values)

    if xscale == "log":
        mask &= taus > 0
    if yscale == "log":
        mask &= y_values > 0

    filtered_taus = taus[mask]
    filtered_y_values = y_values[mask]
    dropped_points = int(mask.size - np.count_nonzero(mask))

    if filtered_taus.size == 0:
        raise ValueError(
            "No data points can be drawn with the current axis settings. "
            "If the dataset is nearly constant, switch the Y axis to Linear."
        )

    return filtered_taus, filtered_y_values, dropped_points


def build_y_axis_label(variance_mode: str, display_mode: str) -> str:
    return f"{NORMALIZATION_LABELS[variance_mode]} {DISPLAY_MODE_LABELS[display_mode]}"


def build_plot_title(overlap_mode: str, display_mode: str) -> str:
    return f"{OVERLAP_LABELS[overlap_mode]} {DISPLAY_MODE_LABELS[display_mode]}"


def export_analysis_to_csv(
    path: str | Path,
    result: AllanAnalysisResult,
    source_path: Path | None,
) -> None:
    output_path = Path(path)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "tau_s",
                "allan_variance",
                "allan_deviation",
                "sampling_interval_s",
                "sample_rate_hz",
                "overlap_mode",
                "variance_mode",
                "mean_value",
                "input_column",
                "input_samples",
                "skipped_rows",
                "source_file",
            ]
        )

        source_name = source_path.name if source_path is not None else ""
        for tau, avar, adev in zip(result.taus, result.avar, result.adev):
            writer.writerow(
                [
                    f"{tau:.12g}",
                    f"{avar:.12g}",
                    f"{adev:.12g}",
                    f"{result.sampling_interval:.12g}",
                    f"{result.sample_rate:.12g}",
                    result.overlap_mode,
                    result.variance_mode,
                    f"{result.mean_value:.12g}",
                    result.column_index,
                    result.sample_count,
                    result.skipped_rows,
                    source_name,
                ]
            )


class AllanVarianceApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1320x820")
        self.minsize(1080, 700)
        self.configure(bg="#efe7da")

        self.csv_path_var = tk.StringVar()
        self.column_var = tk.StringVar(value="1")
        self.sampling_interval_var = tk.StringVar(value="1.0")
        self.overlap_var = tk.StringVar(value="overlapping")
        self.variance_mode_var = tk.StringVar(value="absolute")
        self.display_mode_var = tk.StringVar(value="deviation")
        self.xscale_display_var = tk.StringVar(value="Log")
        self.yscale_display_var = tk.StringVar(value="Log")
        self.status_var = tk.StringVar(
            value="Select a CSV file and click Analyze. Column 1 is used by default."
        )
        self.summary_var = tk.StringVar(
            value=(
                "Waiting for analysis.\n\n"
                "Notes:\n"
                "- Default plot quantity: Allan deviation\n"
                "- Default tau set: octave\n"
                "- Non-numeric rows are skipped automatically"
            )
        )
        self.last_result: AllanAnalysisResult | None = None
        self.last_file_path: Path | None = None

        self._configure_style()
        self._build_layout()
        self._draw_placeholder()

        if allantools is None:
            self.status_var.set("The allantools package was not detected. Install the dependencies before running an analysis.")

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("Root.TFrame", background="#efe7da")
        style.configure("Panel.TFrame", background="#f7f2ea")
        style.configure("Card.TLabelframe", background="#f7f2ea", borderwidth=1)
        style.configure("Card.TLabelframe.Label", background="#f7f2ea", foreground="#2d2a26")
        style.configure("Panel.TLabel", background="#f7f2ea", foreground="#2d2a26")
        style.configure("Muted.TLabel", background="#f7f2ea", foreground="#5f5a53")
        style.configure("Panel.TButton", padding=(10, 6), background="#e9e1d4")
        style.configure(
            "Accent.TButton",
            padding=(12, 8),
            background="#0f766e",
            foreground="#ffffff",
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#0c5f58"), ("pressed", "#0c5f58")],
            foreground=[("active", "#ffffff"), ("pressed", "#ffffff")],
        )
        style.configure("Panel.TRadiobutton", background="#f7f2ea", foreground="#2d2a26")
        style.configure("Panel.TEntry", fieldbackground="#fffdf8")
        style.configure("Panel.TCombobox", fieldbackground="#fffdf8")

    def _build_layout(self) -> None:
        root = ttk.Frame(self, style="Root.TFrame", padding=16)
        root.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        control_panel = ttk.Frame(root, style="Panel.TFrame", padding=18)
        control_panel.grid(row=0, column=0, sticky="nsw", padx=(0, 16))
        plot_panel = ttk.Frame(root, style="Panel.TFrame", padding=18)
        plot_panel.grid(row=0, column=1, sticky="nsew")
        plot_panel.columnconfigure(0, weight=1)
        plot_panel.rowconfigure(0, weight=1)

        self._build_control_panel(control_panel)
        self._build_plot_panel(plot_panel)

    def _build_control_panel(self, parent: ttk.Frame) -> None:
        file_frame = ttk.LabelFrame(parent, text="Input File", style="Card.TLabelframe", padding=12)
        file_frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        file_frame.columnconfigure(0, weight=1)

        ttk.Label(file_frame, text="CSV file", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(file_frame, textvariable=self.csv_path_var, style="Panel.TEntry").grid(
            row=1, column=0, sticky="ew", pady=(6, 8)
        )
        ttk.Button(
            file_frame,
            text="Browse...",
            style="Panel.TButton",
            command=self.browse_file,
        ).grid(row=1, column=1, sticky="e", padx=(8, 0), pady=(6, 8))

        ttk.Label(file_frame, text="Data column (1-based index)", style="Panel.TLabel").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Entry(
            file_frame,
            textvariable=self.column_var,
            width=10,
            style="Panel.TEntry",
        ).grid(row=3, column=0, sticky="w", pady=(6, 0))

        analysis_frame = ttk.LabelFrame(parent, text="Analysis Settings", style="Card.TLabelframe", padding=12)
        analysis_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        analysis_frame.columnconfigure(0, weight=1)

        ttk.Label(analysis_frame, text="Sampling interval t (s)", style="Panel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(
            analysis_frame,
            textvariable=self.sampling_interval_var,
            style="Panel.TEntry",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 12))

        ttk.Label(analysis_frame, text="Computation mode", style="Panel.TLabel").grid(
            row=2, column=0, sticky="w"
        )
        ttk.Radiobutton(
            analysis_frame,
            text="Overlapping (default)",
            value="overlapping",
            variable=self.overlap_var,
            style="Panel.TRadiobutton",
        ).grid(row=3, column=0, sticky="w", pady=(6, 2))
        ttk.Radiobutton(
            analysis_frame,
            text="Non-overlapping",
            value="non_overlapping",
            variable=self.overlap_var,
            style="Panel.TRadiobutton",
        ).grid(row=4, column=0, sticky="w", pady=(0, 12))

        ttk.Label(analysis_frame, text="Normalization", style="Panel.TLabel").grid(
            row=5, column=0, sticky="w"
        )
        ttk.Radiobutton(
            analysis_frame,
            text="Absolute",
            value="absolute",
            variable=self.variance_mode_var,
            style="Panel.TRadiobutton",
        ).grid(row=6, column=0, sticky="w", pady=(6, 2))
        ttk.Radiobutton(
            analysis_frame,
            text="Relative",
            value="relative",
            variable=self.variance_mode_var,
            style="Panel.TRadiobutton",
        ).grid(row=7, column=0, sticky="w")

        ttk.Label(analysis_frame, text="Displayed quantity", style="Panel.TLabel").grid(
            row=8, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Radiobutton(
            analysis_frame,
            text="Allan deviation (default)",
            value="deviation",
            variable=self.display_mode_var,
            style="Panel.TRadiobutton",
            command=self._refresh_plot_from_controls,
        ).grid(row=9, column=0, sticky="w", pady=(6, 2))
        ttk.Radiobutton(
            analysis_frame,
            text="Allan variance",
            value="variance",
            variable=self.display_mode_var,
            style="Panel.TRadiobutton",
            command=self._refresh_plot_from_controls,
        ).grid(row=10, column=0, sticky="w")

        axis_frame = ttk.LabelFrame(parent, text="Axes", style="Card.TLabelframe", padding=12)
        axis_frame.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        axis_frame.columnconfigure(1, weight=1)

        ttk.Label(axis_frame, text="X axis", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        x_combo = ttk.Combobox(
            axis_frame,
            textvariable=self.xscale_display_var,
            state="readonly",
            values=list(SCALE_LABELS.keys()),
            style="Panel.TCombobox",
        )
        x_combo.grid(row=0, column=1, sticky="ew", pady=(0, 8))
        x_combo.bind("<<ComboboxSelected>>", self._refresh_plot_from_controls)

        ttk.Label(axis_frame, text="Y axis", style="Panel.TLabel").grid(row=1, column=0, sticky="w")
        y_combo = ttk.Combobox(
            axis_frame,
            textvariable=self.yscale_display_var,
            state="readonly",
            values=list(SCALE_LABELS.keys()),
            style="Panel.TCombobox",
        )
        y_combo.grid(row=1, column=1, sticky="ew")
        y_combo.bind("<<ComboboxSelected>>", self._refresh_plot_from_controls)

        action_frame = ttk.Frame(parent, style="Panel.TFrame")
        action_frame.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        action_frame.columnconfigure(0, weight=1)

        ttk.Button(
            action_frame,
            text="Analyze",
            style="Accent.TButton",
            command=self.run_analysis,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.export_button = ttk.Button(
            action_frame,
            text="Export Results CSV",
            style="Panel.TButton",
            command=self.export_results,
            state="disabled",
        )
        self.export_button.grid(row=1, column=0, sticky="ew")

        summary_frame = ttk.LabelFrame(parent, text="Summary", style="Card.TLabelframe", padding=12)
        summary_frame.grid(row=4, column=0, sticky="ew")
        summary_frame.columnconfigure(0, weight=1)

        ttk.Label(
            summary_frame,
            textvariable=self.summary_var,
            style="Muted.TLabel",
            justify="left",
        ).grid(row=0, column=0, sticky="w")

        status_frame = ttk.LabelFrame(parent, text="Status", style="Card.TLabelframe", padding=12)
        status_frame.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        status_frame.columnconfigure(0, weight=1)

        ttk.Label(
            status_frame,
            textvariable=self.status_var,
            style="Muted.TLabel",
            justify="left",
            wraplength=300,
        ).grid(row=0, column=0, sticky="w")

    def _build_plot_panel(self, parent: ttk.Frame) -> None:
        self.figure = Figure(figsize=(8.8, 6.4), dpi=100, facecolor="#fcfaf6")
        self.axes = self.figure.add_subplot(111)
        self.axes.set_facecolor("#fcfaf6")

        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.grid(row=0, column=0, sticky="nsew")

        toolbar_frame = ttk.Frame(parent, style="Panel.TFrame")
        toolbar_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side=tk.LEFT)

    def browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a CSV file",
            filetypes=[
                ("CSV files", "*.csv"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.csv_path_var.set(path)
            self.status_var.set(f"Selected file: {Path(path).name}")

    def run_analysis(self) -> None:
        if allantools is None:
            messagebox.showerror(
                "Missing dependency",
                "The allantools package was not detected.\n\nPlease run:\n"
                f"{INSTALL_HINT}",
            )
            self.status_var.set("Analysis did not start because allantools is not installed.")
            return

        csv_path = self.csv_path_var.get().strip()
        if not csv_path:
            messagebox.showwarning("Missing input file", "Please select a CSV file first.")
            return

        try:
            column_index = int(self.column_var.get().strip())
            sampling_interval = float(self.sampling_interval_var.get().strip())
            data, skipped_rows = load_numeric_csv_column(csv_path, column_index)
            result = compute_allan_variance(
                data=data,
                sampling_interval=sampling_interval,
                overlap_mode=self.overlap_var.get(),
                variance_mode=self.variance_mode_var.get(),
                column_index=column_index,
                skipped_rows=skipped_rows,
            )

            self.last_result = result
            self.last_file_path = Path(csv_path)
            self.export_button.state(["!disabled"])
            self._update_summary(result, self.last_file_path)

            try:
                self._render_plot(result)
                self.status_var.set(
                    f"Analysis complete: {self.last_file_path.name}, {result.sample_count} samples loaded."
                )
            except Exception as plot_exc:
                self._draw_placeholder()
                self.status_var.set(f"Analysis complete, but the plot could not be drawn: {plot_exc}")
                messagebox.showwarning("Plot warning", str(plot_exc))
        except Exception as exc:
            self.last_result = None
            self.last_file_path = None
            self.export_button.state(["disabled"])
            self._draw_placeholder()
            self.summary_var.set("Analysis failed.\n\nCheck the CSV column index, sampling interval, and data content.")
            self.status_var.set(f"Analysis failed: {exc}")
            messagebox.showerror("Analysis failed", str(exc))

    def export_results(self) -> None:
        if self.last_result is None:
            messagebox.showwarning("No result", "Run an analysis before exporting the results.")
            return

        default_name = "allan_results.csv"
        if self.last_file_path is not None:
            default_name = f"{self.last_file_path.stem}_allan_results.csv"

        path = filedialog.asksaveasfilename(
            title="Export analysis results",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[
                ("CSV files", "*.csv"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        try:
            export_analysis_to_csv(path, self.last_result, self.last_file_path)
            self.status_var.set(f"Results exported: {Path(path).name}")
            messagebox.showinfo("Export complete", f"Results saved to:\n{path}")
        except Exception as exc:
            self.status_var.set(f"Export failed: {exc}")
            messagebox.showerror("Export failed", str(exc))

    def _refresh_plot_from_controls(self, _event: tk.Event | None = None) -> None:
        if self.last_result is None:
            return
        try:
            self._render_plot(self.last_result)
            self._update_summary(self.last_result, self.last_file_path)
            self.status_var.set("Plot updated with the current settings.")
        except Exception as exc:
            self._draw_placeholder()
            self._update_summary(self.last_result, self.last_file_path)
            self.status_var.set(f"Plot update failed: {exc}")

    def _render_plot(self, result: AllanAnalysisResult) -> None:
        xscale = SCALE_LABELS[self.xscale_display_var.get()]
        yscale = SCALE_LABELS[self.yscale_display_var.get()]
        display_mode = self.display_mode_var.get()
        y_values = result.adev if display_mode == "deviation" else result.avar
        taus, y_values, dropped_points = filter_points_for_scale(
            result.taus,
            y_values,
            xscale,
            yscale,
        )
        result.dropped_points = dropped_points

        self.axes.clear()
        self.axes.set_facecolor("#fcfaf6")
        self.axes.plot(
            taus,
            y_values,
            color="#0f766e",
            linewidth=1.8,
            marker="o",
            markersize=4.6,
            markerfacecolor="#f59e0b",
            markeredgecolor="#0f766e",
        )
        self.axes.set_xscale(xscale)
        self.axes.set_yscale(yscale)
        self.axes.grid(True, which="both", linestyle="--", linewidth=0.7, alpha=0.35)
        self.axes.set_xlabel("Tau (s)")
        self.axes.set_ylabel(build_y_axis_label(result.variance_mode, display_mode))
        self.axes.set_title(build_plot_title(result.overlap_mode, display_mode), loc="left", fontsize=14, pad=10)

        note = (
            f"N = {result.sample_count}\n"
            f"dt = {result.sampling_interval:g} s\n"
            f"rate = {result.sample_rate:g} Hz"
        )
        self.axes.text(
            0.98,
            0.03,
            note,
            transform=self.axes.transAxes,
            ha="right",
            va="bottom",
            fontsize=9,
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": "#fff5dc",
                "edgecolor": "#d9c38f",
            },
        )

        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _update_summary(self, result: AllanAnalysisResult, file_path: Path | None) -> None:
        visible_points = result.taus.size - result.dropped_points
        lines = []
        if file_path is not None:
            lines.append(f"File: {file_path.name}")
        lines.extend(
            [
                f"Samples: {result.sample_count}",
                f"Column: {result.column_index}",
                f"Sampling interval: {result.sampling_interval:g} s",
                f"Sample rate: {result.sample_rate:g} Hz",
                f"Mean value: {result.mean_value:.6g}",
                f"Method: {OVERLAP_LABELS[result.overlap_mode]}",
                f"Normalization: {NORMALIZATION_LABELS[result.variance_mode]}",
                f"Displayed quantity: {DISPLAY_MODE_LABELS[self.display_mode_var.get()]}",
                f"Tau points shown: {visible_points}/{result.taus.size}",
                f"Skipped rows: {result.skipped_rows}",
                f"Axes: X={self.xscale_display_var.get()}, Y={self.yscale_display_var.get()}",
            ]
        )
        if result.dropped_points:
            lines.append(f"Note: {result.dropped_points} points were hidden by the current axis settings.")
        self.summary_var.set("\n".join(lines))

    def _draw_placeholder(self) -> None:
        self.axes.clear()
        self.axes.set_facecolor("#fcfaf6")
        self.axes.text(
            0.5,
            0.55,
            "Select a CSV file and click Analyze",
            ha="center",
            va="center",
            fontsize=16,
            color="#2d2a26",
            transform=self.axes.transAxes,
        )
        self.axes.text(
            0.5,
            0.45,
            "Configure the sampling interval, method, normalization, displayed quantity, and axis scales on the left.",
            ha="center",
            va="center",
            fontsize=10,
            color="#6b645c",
            transform=self.axes.transAxes,
        )
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        for spine in self.axes.spines.values():
            spine.set_visible(False)
        self.figure.tight_layout()
        self.canvas.draw_idle()


def main() -> None:
    app = AllanVarianceApp()
    app.mainloop()


if __name__ == "__main__":
    main()
