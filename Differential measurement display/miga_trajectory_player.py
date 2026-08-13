from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Dict, List, Optional
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import matplotlib as mpl
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


WORKBOOK_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}


mpl.rcParams.update(
    {
        "font.family": ["Times New Roman", "DejaVu Serif"],
        "axes.titlesize": 14,
        "axes.labelsize": 12,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
    }
)


@dataclass(frozen=True)
class TrajectoryData:
    x_values: List[float]
    y_values: List[float]

    @property
    def total_points(self) -> int:
        return len(self.x_values)


def get_column_letters(cell_ref: str) -> str:
    letters: List[str] = []
    for char in cell_ref:
        if char.isalpha():
            letters.append(char)
        else:
            break
    return "".join(letters)


def load_shared_strings(workbook: ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []

    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    strings: List[str] = []
    for item in root.findall("main:si", WORKBOOK_NS):
        text_parts = [node.text or "" for node in item.findall(".//main:t", WORKBOOK_NS)]
        strings.append("".join(text_parts))
    return strings


def resolve_first_sheet_path(workbook: ZipFile) -> str:
    workbook_xml = ET.fromstring(workbook.read("xl/workbook.xml"))
    first_sheet = workbook_xml.find("main:sheets/main:sheet", WORKBOOK_NS)
    if first_sheet is None:
        raise ValueError("No worksheet was found in demo.xlsx.")

    rel_id = first_sheet.attrib.get(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    )
    if not rel_id:
        raise ValueError("The first worksheet is missing a relationship id.")

    relationships_xml = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    for relation in relationships_xml.findall("rel:Relationship", REL_NS):
        if relation.attrib.get("Id") != rel_id:
            continue

        target = relation.attrib.get("Target", "")
        if target.startswith("/"):
            return target.lstrip("/")
        return f"xl/{target}"

    raise ValueError("Could not resolve the first worksheet path.")


def read_cell_value(cell: ET.Element, shared_strings: List[str]) -> Optional[str]:
    cell_type = cell.attrib.get("t")
    value_node = cell.find("main:v", WORKBOOK_NS)

    if cell_type == "s" and value_node is not None:
        return shared_strings[int(value_node.text)]

    if cell_type == "inlineStr":
        text_node = cell.find("main:is/main:t", WORKBOOK_NS)
        return text_node.text if text_node is not None else None

    if value_node is not None:
        return value_node.text

    return None


def load_trajectory_data(excel_path: Path) -> TrajectoryData:
    if not excel_path.exists():
        raise FileNotFoundError(f"Data file was not found: {excel_path}")

    x_values: List[float] = []
    y_values: List[float] = []

    with ZipFile(excel_path) as workbook:
        shared_strings = load_shared_strings(workbook)
        sheet_path = resolve_first_sheet_path(workbook)
        sheet_xml = ET.fromstring(workbook.read(sheet_path))
        sheet_data = sheet_xml.find("main:sheetData", WORKBOOK_NS)
        if sheet_data is None:
            raise ValueError("The first worksheet does not contain any rows.")

        for row in sheet_data.findall("main:row", WORKBOOK_NS):
            cell_map: Dict[str, Optional[str]] = {}
            for cell in row.findall("main:c", WORKBOOK_NS):
                cell_ref = cell.attrib.get("r", "")
                column = get_column_letters(cell_ref)
                if column in {"A", "B"}:
                    cell_map[column] = read_cell_value(cell, shared_strings)

            if "A" not in cell_map or "B" not in cell_map:
                continue

            try:
                x_values.append(float(cell_map["A"]))
                y_values.append(float(cell_map["B"]))
            except (TypeError, ValueError):
                continue

    if not x_values or not y_values:
        raise ValueError("No numeric data was found in the first two columns of demo.xlsx.")

    return TrajectoryData(x_values=x_values, y_values=y_values)


class TrajectoryPlayerApp(tk.Tk):
    def __init__(self, data_file: Path, trajectory: TrajectoryData) -> None:
        super().__init__()
        self.data_file = data_file
        self.trajectory = trajectory
        self.visible_count = 1
        self.is_playing = False
        self.after_id: Optional[str] = None
        self.is_syncing_slider = False

        self.position_var = tk.DoubleVar(value=1.0)
        self.speed_var = tk.DoubleVar(value=25.0)
        self.status_var = tk.StringVar()
        self.coordinate_var = tk.StringVar()
        self.speed_label_var = tk.StringVar()

        self.title("MIGA Differential Trajectory Player")
        self.geometry("1220x760")
        self.minsize(980, 640)
        self.configure(bg="#f5f6f7")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._configure_styles()
        self._build_layout()
        self._set_axes_limits()
        self._refresh_plot()

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", font=("Segoe UI", 10))
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Panel.TLabelframe", background="#ffffff")
        style.configure("Panel.TLabelframe.Label", background="#ffffff", font=("Segoe UI", 10, "bold"))
        style.configure("Header.TLabel", background="#ffffff", font=("Segoe UI", 12, "bold"))
        style.configure("Muted.TLabel", background="#ffffff", foreground="#4b5563")
        style.configure("Value.TLabel", background="#ffffff", font=("Consolas", 10))
        style.configure("Primary.TButton", padding=(12, 6))

    def _build_layout(self) -> None:
        root = ttk.Frame(self, padding=14, style="Card.TFrame")
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=4)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        plot_panel = ttk.Frame(root, padding=10, style="Card.TFrame")
        plot_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        plot_panel.rowconfigure(0, weight=1)
        plot_panel.columnconfigure(0, weight=1)

        control_panel = ttk.Frame(root, padding=10, style="Card.TFrame")
        control_panel.grid(row=0, column=1, sticky="nsew")
        control_panel.columnconfigure(0, weight=1)

        self.figure = Figure(figsize=(8.2, 6.4), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Trajectory Playback", pad=14)
        self.ax.set_xlabel("MIGA22")
        self.ax.set_ylabel("MIGA21")
        self.ax.set_facecolor("#fcfcfd")
        self.ax.grid(True, linestyle="--", linewidth=0.6, color="#b4bcc6", alpha=0.7)
        self.ax.set_aspect("equal", adjustable="box")

        self.line_handle, = self.ax.plot(
            [], [],
            color="#0b3c5d",
            linewidth=1.6,
            label="Trajectory",
        )
        self.current_point_handle, = self.ax.plot(
            [], [],
            marker="o",
            markersize=7,
            color="#c0392b",
            linestyle="None",
            label="Current sample",
        )
        self.start_point_handle, = self.ax.plot(
            [self.trajectory.x_values[0]],
            [self.trajectory.y_values[0]],
            marker="s",
            markersize=5,
            color="#1f7a8c",
            linestyle="None",
            label="Start",
        )
        self.ax.legend(loc="upper right", frameon=True, edgecolor="#d0d7de")

        canvas = FigureCanvasTkAgg(self.figure, master=plot_panel)
        self.canvas = canvas
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        info_frame = ttk.LabelFrame(control_panel, text="Dataset", style="Panel.TLabelframe", padding=12)
        info_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        info_frame.columnconfigure(0, weight=1)
        ttk.Label(info_frame, text="Source file", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(info_frame, text=self.data_file.name, style="Value.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 8))
        ttk.Label(info_frame, text="Samples", style="Muted.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(info_frame, text=str(self.trajectory.total_points), style="Value.TLabel").grid(row=3, column=0, sticky="w")

        playback_frame = ttk.LabelFrame(control_panel, text="Playback", style="Panel.TLabelframe", padding=12)
        playback_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        playback_frame.columnconfigure(0, weight=1)
        playback_frame.columnconfigure(1, weight=1)
        playback_frame.columnconfigure(2, weight=1)

        ttk.Button(playback_frame, text="Play", command=self.play, style="Primary.TButton").grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(playback_frame, text="Pause", command=self.pause, style="Primary.TButton").grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Button(playback_frame, text="Reset", command=self.reset, style="Primary.TButton").grid(row=0, column=2, sticky="ew", padx=(6, 0))

        ttk.Label(playback_frame, text="Sample index", style="Muted.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(12, 2))
        self.position_scale = ttk.Scale(
            playback_frame,
            from_=1,
            to=self.trajectory.total_points,
            orient="horizontal",
            variable=self.position_var,
            command=self.on_position_change,
        )
        self.position_scale.grid(row=2, column=0, columnspan=3, sticky="ew")
        ttk.Label(playback_frame, textvariable=self.status_var, style="Value.TLabel").grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

        ttk.Label(playback_frame, text="Playback speed", style="Muted.TLabel").grid(row=4, column=0, columnspan=3, sticky="w", pady=(14, 2))
        self.speed_scale = ttk.Scale(
            playback_frame,
            from_=1,
            to=120,
            orient="horizontal",
            variable=self.speed_var,
            command=self.on_speed_change,
        )
        self.speed_scale.grid(row=5, column=0, columnspan=3, sticky="ew")
        ttk.Label(playback_frame, textvariable=self.speed_label_var, style="Value.TLabel").grid(row=6, column=0, columnspan=3, sticky="w", pady=(6, 0))

        point_frame = ttk.LabelFrame(control_panel, text="Current Point", style="Panel.TLabelframe", padding=12)
        point_frame.grid(row=2, column=0, sticky="ew")
        point_frame.columnconfigure(0, weight=1)
        ttk.Label(point_frame, text="Coordinates", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(point_frame, textvariable=self.coordinate_var, style="Value.TLabel", justify="left").grid(row=1, column=0, sticky="w", pady=(4, 0))

        notes_frame = ttk.LabelFrame(control_panel, text="Notes", style="Panel.TLabelframe", padding=12)
        notes_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        notes_frame.columnconfigure(0, weight=1)
        ttk.Label(
            notes_frame,
            text="Playback follows the worksheet order from top to bottom.\nAxes stay fixed to the full data range for consistent comparison.",
            style="Muted.TLabel",
            justify="left",
        ).grid(row=0, column=0, sticky="w")

    def _set_axes_limits(self) -> None:
        self.ax.set_xlim(*self._compute_limits(self.trajectory.x_values))
        self.ax.set_ylim(*self._compute_limits(self.trajectory.y_values))

    @staticmethod
    def _compute_limits(values: List[float]) -> tuple[float, float]:
        lower = min(values)
        upper = max(values)
        span = upper - lower
        if span == 0:
            margin = max(abs(lower) * 0.05, 1.0)
        else:
            margin = span * 0.05
        return lower - margin, upper + margin

    def _refresh_plot(self) -> None:
        count = max(1, min(self.visible_count, self.trajectory.total_points))
        x_slice = self.trajectory.x_values[:count]
        y_slice = self.trajectory.y_values[:count]

        self.line_handle.set_data(x_slice, y_slice)
        self.current_point_handle.set_data([x_slice[-1]], [y_slice[-1]])

        self.status_var.set(f"Sample {count} / {self.trajectory.total_points}")
        self.coordinate_var.set(f"MIGA22 = {x_slice[-1]:.4f}\nMIGA21 = {y_slice[-1]:.4f}")
        self.speed_label_var.set(f"{self.speed_var.get():.1f} samples / s")
        self.canvas.draw_idle()

    def _set_visible_count(self, count: int, sync_slider: bool = True) -> None:
        self.visible_count = max(1, min(count, self.trajectory.total_points))
        if sync_slider:
            self.is_syncing_slider = True
            self.position_var.set(float(self.visible_count))
            self.is_syncing_slider = False
        self._refresh_plot()

    def play(self) -> None:
        if self.visible_count >= self.trajectory.total_points:
            self._set_visible_count(1)

        if self.is_playing:
            return

        self.is_playing = True
        self._schedule_next_step()

    def pause(self) -> None:
        self.is_playing = False
        if self.after_id is not None:
            self.after_cancel(self.after_id)
            self.after_id = None

    def reset(self) -> None:
        self.pause()
        self._set_visible_count(1)

    def _schedule_next_step(self) -> None:
        if not self.is_playing:
            return

        delay_ms = max(8, int(1000 / max(self.speed_var.get(), 1.0)))
        self.after_id = self.after(delay_ms, self._advance_one_step)

    def _advance_one_step(self) -> None:
        if not self.is_playing:
            return

        if self.visible_count < self.trajectory.total_points:
            self._set_visible_count(self.visible_count + 1)
            self._schedule_next_step()
            return

        self.pause()

    def on_position_change(self, value: str) -> None:
        if self.is_syncing_slider:
            return

        self.pause()
        self._set_visible_count(int(round(float(value))), sync_slider=False)

    def on_speed_change(self, _value: str) -> None:
        self.speed_label_var.set(f"{self.speed_var.get():.1f} samples / s")

    def on_close(self) -> None:
        self.pause()
        self.destroy()


def main() -> None:
    data_file = Path(__file__).resolve().with_name("demo.xlsx")
    try:
        trajectory = load_trajectory_data(data_file)
    except Exception as exc:
        hidden_root = tk.Tk()
        hidden_root.withdraw()
        messagebox.showerror("Data Loading Error", str(exc))
        hidden_root.destroy()
        return

    app = TrajectoryPlayerApp(data_file, trajectory)
    app.mainloop()


if __name__ == "__main__":
    main()
