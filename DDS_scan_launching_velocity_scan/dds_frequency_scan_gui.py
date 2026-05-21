#!/usr/bin/env python3
"""GUI tool to generate DDS launch-frequency scan XML files."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


XML_ENCODING = "ISO-8859-1"
DEFAULT_CENTER_MHZ = Decimal("111.1")
DEFAULT_DELTA_MHZ = Decimal("6.210")
DEFAULT_SCAN_CH0_FREQ_MHZ = DEFAULT_CENTER_MHZ - DEFAULT_DELTA_MHZ / Decimal("2")
DEFAULT_SCAN_CH1_FREQ_MHZ = DEFAULT_CENTER_MHZ + DEFAULT_DELTA_MHZ / Decimal("2")


@dataclass
class ChannelSetting:
    frequency_mhz: Decimal
    amplitude: int


def parse_decimal(text: str, field_name: str) -> Decimal:
    try:
        return Decimal(text.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"Invalid number for {field_name}: {text!r}") from exc


def parse_int(text: str, field_name: str) -> int:
    try:
        return int(text.strip())
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid integer for {field_name}: {text!r}") from exc


def decimal_range(start: Decimal, end: Decimal, step: Decimal) -> list[Decimal]:
    if step == 0:
        raise ValueError("Step must not be zero.")

    if start < end and step < 0:
        raise ValueError("Step must be positive when start < end.")
    if start > end and step > 0:
        raise ValueError("Step must be negative when start > end.")

    values: list[Decimal] = []
    current = start

    if step > 0:
        while current <= end:
            values.append(current)
            current += step
    else:
        while current >= end:
            values.append(current)
            current += step

    return values


def integer_range(start: int, end: int, step: int) -> list[int]:
    if step == 0:
        raise ValueError("Step must not be zero.")

    if start < end and step < 0:
        raise ValueError("Step must be positive when start < end.")
    if start > end and step > 0:
        raise ValueError("Step must be negative when start > end.")

    values: list[int] = []
    current = start

    if step > 0:
        while current <= end:
            values.append(current)
            current += step
    else:
        while current >= end:
            values.append(current)
            current += step

    return values


def format_hz_from_mhz(value_mhz: Decimal) -> str:
    value_hz = value_mhz * Decimal("1000000")
    return f"{value_hz:.1f}"


def format_delta_comment(value_mhz: Decimal) -> str:
    text = format(value_mhz, "f")
    if "." not in text:
        return f"{text}.000"

    whole, frac = text.split(".", 1)
    frac = frac.rstrip("0")
    if len(frac) < 3:
        frac = frac.ljust(3, "0")
    return f"{whole}.{frac}"


def render_elem(
    n_value: int,
    ch0: ChannelSetting,
    ch1: ChannelSetting,
    comment_text: str | None = None,
) -> list[str]:
    lines: list[str] = []
    if comment_text is not None:
        lines.append(f"  <!-- {comment_text} -->")

    lines.extend(
        [
            f'  <elem n="{n_value}">',
            "    <ch0>",
            "      <mode>sf</mode>",
            f"      <fr>{format_hz_from_mhz(ch0.frequency_mhz)}</fr>",
            f"      <am>{ch0.amplitude}</am>",
            "    </ch0>",
            "    <ch1>",
            "      <mode>sf</mode>",
            f"      <fr>{format_hz_from_mhz(ch1.frequency_mhz)}</fr>",
            f"      <am>{ch1.amplitude}</am>",
            "    </ch1>",
            "  </elem>",
        ]
    )
    return lines


def validate_scan_start_n(scan_start_n: int, include_cooling: bool) -> None:
    if include_cooling and scan_start_n == 0:
        raise ValueError('When "Include cooling n=0" is enabled, first scan n cannot be 0.')


def build_xml_document(
    scan_blocks: list[list[str]],
    include_cooling: bool,
    cooling_frequency_mhz: Decimal,
    cooling_ch0_am: int,
    cooling_ch1_am: int,
) -> str:
    lines = [
        f"<?xml version='1.0' encoding='{XML_ENCODING}'?>",
        "",
        "<ad9958>",
    ]

    if include_cooling:
        lines.extend(
            render_elem(
                n_value=0,
                ch0=ChannelSetting(
                    frequency_mhz=cooling_frequency_mhz, amplitude=cooling_ch0_am
                ),
                ch1=ChannelSetting(
                    frequency_mhz=cooling_frequency_mhz, amplitude=cooling_ch1_am
                ),
            )
        )
        lines.append("")

    for block in scan_blocks:
        lines.extend(block)
        lines.append("")

    if lines[-1] == "":
        lines.pop()
    lines.append("</ad9958>")
    lines.append("")
    return "\n".join(lines)


def build_delta_frequency_scan_xml_text(
    delta_start_mhz: Decimal,
    delta_end_mhz: Decimal,
    delta_step_mhz: Decimal,
    scan_start_n: int,
    center_mhz: Decimal,
    include_cooling: bool,
    cooling_ch0_am: int,
    cooling_ch1_am: int,
    scan_ch0_am: int,
    scan_ch1_am: int,
) -> str:
    validate_scan_start_n(scan_start_n, include_cooling)

    deltas = decimal_range(delta_start_mhz, delta_end_mhz, delta_step_mhz)
    scan_blocks: list[list[str]] = []

    for index, delta_mhz in enumerate(deltas):
        up_mhz = center_mhz - delta_mhz / Decimal("2")
        down_mhz = center_mhz + delta_mhz / Decimal("2")
        scan_blocks.append(
            render_elem(
                n_value=scan_start_n + index,
                ch0=ChannelSetting(frequency_mhz=up_mhz, amplitude=scan_ch0_am),
                ch1=ChannelSetting(frequency_mhz=down_mhz, amplitude=scan_ch1_am),
                comment_text=f"Frequency delta {format_delta_comment(delta_mhz)} MHz",
            )
        )

    return build_xml_document(
        scan_blocks=scan_blocks,
        include_cooling=include_cooling,
        cooling_frequency_mhz=center_mhz,
        cooling_ch0_am=cooling_ch0_am,
        cooling_ch1_am=cooling_ch1_am,
    )


def build_am_scan_xml_text(
    scan_channel: str,
    am_start: int,
    am_end: int,
    am_step: int,
    scan_start_n: int,
    include_cooling: bool,
    cooling_frequency_mhz: Decimal,
    cooling_ch0_am: int,
    cooling_ch1_am: int,
    fixed_ch0_frequency_mhz: Decimal,
    fixed_ch1_frequency_mhz: Decimal,
    fixed_ch0_am: int,
    fixed_ch1_am: int,
) -> str:
    validate_scan_start_n(scan_start_n, include_cooling)

    if scan_channel not in {"ch0", "ch1"}:
        raise ValueError(f"Unknown scan channel: {scan_channel}")

    amplitudes = integer_range(am_start, am_end, am_step)
    scan_blocks: list[list[str]] = []

    for index, amplitude in enumerate(amplitudes):
        ch0_amplitude = amplitude if scan_channel == "ch0" else fixed_ch0_am
        ch1_amplitude = amplitude if scan_channel == "ch1" else fixed_ch1_am
        scan_blocks.append(
            render_elem(
                n_value=scan_start_n + index,
                ch0=ChannelSetting(
                    frequency_mhz=fixed_ch0_frequency_mhz, amplitude=ch0_amplitude
                ),
                ch1=ChannelSetting(
                    frequency_mhz=fixed_ch1_frequency_mhz, amplitude=ch1_amplitude
                ),
                comment_text=f"Scan {scan_channel} amplitude {amplitude}",
            )
        )

    return build_xml_document(
        scan_blocks=scan_blocks,
        include_cooling=include_cooling,
        cooling_frequency_mhz=cooling_frequency_mhz,
        cooling_ch0_am=cooling_ch0_am,
        cooling_ch1_am=cooling_ch1_am,
    )


class DDSFrequencyScanApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("DDS XML Generator")
        self.root.resizable(False, False)

        self.output_path_var = tk.StringVar(
            value=str(Path.cwd() / "dds_frequency_scan.xml")
        )
        self.include_cooling_var = tk.BooleanVar(value=True)
        self.scan_mode_var = tk.StringVar(value="delta_f")
        self.am_scan_channel_var = tk.StringVar(value="ch0")

        self.entries: dict[str, ttk.Entry] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=14)
        frame.grid(row=0, column=0, sticky="nsew")

        description = (
            "Mode 1: scan delta_f with ch0 = center - delta_f / 2 and ch1 = center + delta_f / 2\n"
            "Mode 2: keep ch0/ch1 frequencies fixed and scan the AM of one selected channel."
        )
        ttk.Label(frame, text=description, justify="left").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10)
        )

        row = 1
        ttk.Label(frame, text="Generation mode").grid(row=row, column=0, sticky="w")
        mode_frame = ttk.Frame(frame)
        mode_frame.grid(row=row, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(
            mode_frame,
            text="Scan delta_f",
            variable=self.scan_mode_var,
            value="delta_f",
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            mode_frame,
            text="Fix frequency, scan AM",
            variable=self.scan_mode_var,
            value="am_scan",
        ).grid(row=0, column=1, sticky="w", padx=(12, 0))
        row += 1

        row = self._add_entry(frame, row, "First scan n", "1")
        row = self._add_entry(
            frame, row, "Center / cooling freq (MHz)", format(DEFAULT_CENTER_MHZ, "f")
        )

        delta_frame = ttk.LabelFrame(frame, text="Mode 1: delta_f scan", padding=10)
        delta_frame.grid(row=row, column=0, columnspan=3, sticky="ew")
        delta_row = 0
        delta_row = self._add_entry(
            delta_frame, delta_row, "Delta start (MHz)", format(DEFAULT_DELTA_MHZ, "f")
        )
        delta_row = self._add_entry(
            delta_frame, delta_row, "Delta end (MHz)", format(DEFAULT_DELTA_MHZ, "f")
        )
        delta_row = self._add_entry(delta_frame, delta_row, "Delta step (MHz)", "0.010")
        delta_row = self._add_entry(delta_frame, delta_row, "Scan ch0 am", "36")
        delta_row = self._add_entry(delta_frame, delta_row, "Scan ch1 am", "23")
        ttk.Label(
            delta_frame,
            text="Only these fields are used in delta_f mode.",
            justify="left",
        ).grid(row=delta_row, column=0, columnspan=2, sticky="w", pady=(6, 0))
        row += 1

        am_frame = ttk.LabelFrame(
            frame, text="Mode 2: fixed frequency, scan one channel AM", padding=10
        )
        am_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        am_row = 0
        ttk.Label(am_frame, text="Scanned channel").grid(
            row=am_row, column=0, sticky="w", pady=2
        )
        am_channel_frame = ttk.Frame(am_frame)
        am_channel_frame.grid(row=am_row, column=1, sticky="w", pady=2)
        ttk.Radiobutton(
            am_channel_frame,
            text="ch0",
            variable=self.am_scan_channel_var,
            value="ch0",
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            am_channel_frame,
            text="ch1",
            variable=self.am_scan_channel_var,
            value="ch1",
        ).grid(row=0, column=1, sticky="w", padx=(12, 0))
        am_row += 1
        am_row = self._add_entry(am_frame, am_row, "AM start", "36")
        am_row = self._add_entry(am_frame, am_row, "AM end", "36")
        am_row = self._add_entry(am_frame, am_row, "AM step", "1")
        am_row = self._add_entry(
            am_frame,
            am_row,
            "Fixed ch0 freq (MHz)",
            format(DEFAULT_SCAN_CH0_FREQ_MHZ, "f"),
        )
        am_row = self._add_entry(
            am_frame,
            am_row,
            "Fixed ch1 freq (MHz)",
            format(DEFAULT_SCAN_CH1_FREQ_MHZ, "f"),
        )
        am_row = self._add_entry(am_frame, am_row, "Fixed ch0 am", "36")
        am_row = self._add_entry(am_frame, am_row, "Fixed ch1 am", "23")
        ttk.Label(
            am_frame,
            text="The scanned channel uses the AM range above; the other channel keeps its fixed AM.",
            justify="left",
        ).grid(row=am_row, column=0, columnspan=2, sticky="w", pady=(6, 0))
        row += 1

        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=(10, 10)
        )
        row += 1

        ttk.Checkbutton(
            frame,
            text="Include cooling elem n=0",
            variable=self.include_cooling_var,
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 10))
        row += 1

        ttk.Label(frame, text="Cooling amplitudes").grid(
            row=row, column=0, columnspan=3, sticky="w"
        )
        row += 1
        row = self._add_entry(frame, row, "Cooling ch0 am", "28")
        row = self._add_entry(frame, row, "Cooling ch1 am", "18")

        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=10
        )
        row += 1

        ttk.Label(frame, text="Output XML").grid(row=row, column=0, sticky="w")
        ttk.Entry(frame, width=42, textvariable=self.output_path_var).grid(
            row=row, column=1, sticky="ew", padx=(8, 8)
        )
        ttk.Button(frame, text="Browse", command=self._choose_output_path).grid(
            row=row, column=2, sticky="ew"
        )
        row += 1

        ttk.Button(frame, text="Preview", command=self.preview_xml).grid(
            row=row, column=0, sticky="ew", pady=(10, 0)
        )
        ttk.Button(frame, text="Generate XML", command=self.generate_xml).grid(
            row=row, column=2, sticky="ew", pady=(10, 0)
        )
        row += 1

        self.preview_text = tk.Text(frame, width=74, height=20, wrap="none")
        self.preview_text.grid(
            row=row, column=0, columnspan=3, sticky="nsew", pady=(10, 0)
        )
        self.preview_text.configure(state="disabled")

        frame.columnconfigure(1, weight=1)

    def _add_entry(self, frame: ttk.Frame, row: int, label: str, default: str) -> int:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
        entry = ttk.Entry(frame, width=18)
        entry.insert(0, default)
        entry.grid(row=row, column=1, sticky="w", padx=(8, 0), pady=2)
        self.entries[label] = entry
        return row + 1

    def _choose_output_path(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save XML file",
            defaultextension=".xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
            initialfile=Path(self.output_path_var.get()).name,
        )
        if path:
            self.output_path_var.set(path)

    def _collect_xml_text(self) -> str:
        first_scan_n = parse_int(self.entries["First scan n"].get(), "First scan n")
        center_mhz = parse_decimal(
            self.entries["Center / cooling freq (MHz)"].get(),
            "Center / cooling freq (MHz)",
        )
        cooling_ch0_am = parse_int(
            self.entries["Cooling ch0 am"].get(), "Cooling ch0 am"
        )
        cooling_ch1_am = parse_int(
            self.entries["Cooling ch1 am"].get(), "Cooling ch1 am"
        )
        if self.scan_mode_var.get() == "delta_f":
            delta_start = parse_decimal(
                self.entries["Delta start (MHz)"].get(), "Delta start (MHz)"
            )
            delta_end = parse_decimal(
                self.entries["Delta end (MHz)"].get(), "Delta end (MHz)"
            )
            delta_step = parse_decimal(
                self.entries["Delta step (MHz)"].get(), "Delta step (MHz)"
            )
            scan_ch0_am = parse_int(
                self.entries["Scan ch0 am"].get(), "Scan ch0 am"
            )
            scan_ch1_am = parse_int(
                self.entries["Scan ch1 am"].get(), "Scan ch1 am"
            )

            return build_delta_frequency_scan_xml_text(
                delta_start_mhz=delta_start,
                delta_end_mhz=delta_end,
                delta_step_mhz=delta_step,
                scan_start_n=first_scan_n,
                center_mhz=center_mhz,
                include_cooling=self.include_cooling_var.get(),
                cooling_ch0_am=cooling_ch0_am,
                cooling_ch1_am=cooling_ch1_am,
                scan_ch0_am=scan_ch0_am,
                scan_ch1_am=scan_ch1_am,
            )

        if self.scan_mode_var.get() == "am_scan":
            am_start = parse_int(self.entries["AM start"].get(), "AM start")
            am_end = parse_int(self.entries["AM end"].get(), "AM end")
            am_step = parse_int(self.entries["AM step"].get(), "AM step")
            fixed_ch0_frequency_mhz = parse_decimal(
                self.entries["Fixed ch0 freq (MHz)"].get(), "Fixed ch0 freq (MHz)"
            )
            fixed_ch1_frequency_mhz = parse_decimal(
                self.entries["Fixed ch1 freq (MHz)"].get(), "Fixed ch1 freq (MHz)"
            )
            fixed_ch0_am = parse_int(
                self.entries["Fixed ch0 am"].get(), "Fixed ch0 am"
            )
            fixed_ch1_am = parse_int(
                self.entries["Fixed ch1 am"].get(), "Fixed ch1 am"
            )

            return build_am_scan_xml_text(
                scan_channel=self.am_scan_channel_var.get(),
                am_start=am_start,
                am_end=am_end,
                am_step=am_step,
                scan_start_n=first_scan_n,
                include_cooling=self.include_cooling_var.get(),
                cooling_frequency_mhz=center_mhz,
                cooling_ch0_am=cooling_ch0_am,
                cooling_ch1_am=cooling_ch1_am,
                fixed_ch0_frequency_mhz=fixed_ch0_frequency_mhz,
                fixed_ch1_frequency_mhz=fixed_ch1_frequency_mhz,
                fixed_ch0_am=fixed_ch0_am,
                fixed_ch1_am=fixed_ch1_am,
            )

        raise ValueError(f"Unknown generation mode: {self.scan_mode_var.get()}")

    def preview_xml(self) -> None:
        try:
            xml_text = self._collect_xml_text()
        except ValueError as exc:
            messagebox.showerror("Input error", str(exc))
            return

        self._set_preview_text(xml_text)

    def _set_preview_text(self, xml_text: str) -> None:
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", xml_text)
        self.preview_text.configure(state="disabled")

    def generate_xml(self) -> None:
        try:
            xml_text = self._collect_xml_text()
        except ValueError as exc:
            messagebox.showerror("Input error", str(exc))
            return

        output_path = Path(self.output_path_var.get()).expanduser()
        if not output_path.name:
            messagebox.showerror("Path error", "Please choose an output XML filename.")
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(xml_text, encoding=XML_ENCODING)
        self._set_preview_text(xml_text)
        messagebox.showinfo("Done", f"XML written to:\n{output_path}")


def main() -> None:
    root = tk.Tk()
    app = DDSFrequencyScanApp(root)
    app.preview_xml()
    root.mainloop()


if __name__ == "__main__":
    main()
