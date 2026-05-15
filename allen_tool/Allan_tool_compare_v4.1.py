#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Allan deviation multi-run comparison GUI
Features:
- Add one or multiple allan_deviation.csv files (can add in multiple batches)
- Prompt user to assign a custom legend label on import (default = filename)
- Plot all curves on one log-log chart
- Error display:
    - bar  : symmetric +/- error with caps (top and bottom)
    - band : shaded region (adev +/- err) using the SAME color as the curve
    - none : no error display
- Save figure to PNG/PDF/SVG

CSV required columns:
- tau_s
- allan_deviation
Optional:
- allan_error
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


@dataclass
class AllanSeries:
    path: Path
    label: str
    tau: np.ndarray
    adev: np.ndarray
    err: Optional[np.ndarray]


def read_allan_csv(path: Path) -> AllanSeries:
    df = pd.read_csv(path)

    required = {"tau_s", "allan_deviation"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing required columns {required}. Got: {list(df.columns)}")

    tau = df["tau_s"].to_numpy(dtype=float)
    adev = df["allan_deviation"].to_numpy(dtype=float)
    err = df["allan_error"].to_numpy(dtype=float) if "allan_error" in df.columns else None

    # Clean
    mask = np.isfinite(tau) & np.isfinite(adev) & (tau > 0) & (adev > 0)
    if err is not None:
        mask = mask & np.isfinite(err) & (err >= 0)

    tau, adev = tau[mask], adev[mask]
    if err is not None:
        err = err[mask]

    if len(tau) < 2:
        raise ValueError("Not enough valid points (<2) after cleaning.")

    # Sort by tau
    order = np.argsort(tau)
    tau, adev = tau[order], adev[order]
    if err is not None:
        err = err[order]

    # Label will be assigned by GUI
    return AllanSeries(path=path, label=path.name, tau=tau, adev=adev, err=err)


class AllanCompareApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Allan Deviation Comparison (GUI)")
        self.geometry("1150x720")

        # key: absolute path string
        self.series: Dict[str, AllanSeries] = {}

        self._build_ui()

    def _build_ui(self):
        # Main layout: left controls, right plot
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=10)
        left.grid(row=0, column=0, sticky="ns")
        left.rowconfigure(6, weight=1)

        right = ttk.Frame(self, padding=10)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=0)

        # -------- Left: files list + controls --------
        ttk.Label(left, text="Imported Allan files:").grid(row=0, column=0, sticky="w")

        self.listbox = tk.Listbox(left, width=56, height=18, selectmode=tk.EXTENDED)
        self.listbox.grid(row=1, column=0, sticky="nsew", pady=(6, 6))

        btns = ttk.Frame(left)
        btns.grid(row=2, column=0, sticky="ew")
        btns.columnconfigure((0, 1, 2, 3), weight=1)

        ttk.Button(btns, text="Add files…", command=self.add_files).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Remove selected", command=self.remove_selected).grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Rename selected…", command=self.rename_selected).grid(row=0, column=2, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Clear", command=self.clear_all).grid(row=0, column=3, sticky="ew")

        # Plot options
        opts = ttk.LabelFrame(left, text="Plot options", padding=10)
        opts.grid(row=3, column=0, sticky="ew", pady=(10, 10))
        opts.columnconfigure(1, weight=1)

        ttk.Label(opts, text="Error display:").grid(row=0, column=0, sticky="w")
        self.err_style = tk.StringVar(value="bar")
        ttk.Combobox(
            opts, textvariable=self.err_style,
            values=["bar", "band", "none"], state="readonly", width=10
        ).grid(row=0, column=1, sticky="w", padx=(6, 0))

        ttk.Label(opts, text="Error every N points:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.err_every = tk.IntVar(value=3)
        ttk.Spinbox(opts, from_=1, to=500, textvariable=self.err_every, width=10).grid(
            row=1, column=1, sticky="w", padx=(6, 0), pady=(8, 0)
        )

        self.use_parent_as_label = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts, text="Default label uses parent folder name (results_xxx)",
            variable=self.use_parent_as_label
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        # Title and axis labels
        labels = ttk.LabelFrame(left, text="Title and axis labels", padding=10)
        labels.grid(row=4, column=0, sticky="ew")
        labels.columnconfigure(1, weight=1)

        self.title_var = tk.StringVar(value="Allan Deviation Comparison")
        self.xlabel_var = tk.StringVar(value=r"$\tau$ (s)")
        self.ylabel_var = tk.StringVar(value="Allan Deviation")

        ttk.Label(labels, text="Title:").grid(row=0, column=0, sticky="w")
        ttk.Entry(labels, textvariable=self.title_var, width=46).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        ttk.Label(labels, text="X label:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(labels, textvariable=self.xlabel_var, width=46).grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))

        ttk.Label(labels, text="Y label:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(labels, textvariable=self.ylabel_var, width=46).grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))

        # Actions
        actions = ttk.Frame(left)
        actions.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        actions.columnconfigure((0, 1), weight=1)

        ttk.Button(actions, text="Plot / Refresh", command=self.plot).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="Save figure…", command=self.save_figure).grid(row=0, column=1, sticky="ew")

        # Status
        self.status = tk.StringVar(value="Ready. Click 'Add files…' to import allan_deviation.csv (multiple batches supported).")
        ttk.Label(left, textvariable=self.status, foreground="#444").grid(row=7, column=0, sticky="w", pady=(10, 0))

        # -------- Right: Matplotlib area (NO grid/pack mixing in same container) --------
        plot_frame = ttk.Frame(right)
        plot_frame.grid(row=0, column=0, sticky="nsew")
        plot_frame.rowconfigure(0, weight=1)
        plot_frame.columnconfigure(0, weight=1)

        toolbar_frame = ttk.Frame(right)
        toolbar_frame.grid(row=1, column=0, sticky="ew")

        self.fig = Figure(figsize=(7.8, 5.6), dpi=100)
        self.ax = self.fig.add_subplot(111)

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()

    def _set_status(self, text: str):
        self.status.set(text)

    def _default_label_for_path(self, p: Path) -> str:
        if self.use_parent_as_label.get():
            return p.parent.name if p.parent.name else p.name
        return p.name

    def _prompt_label(self, default: str) -> Optional[str]:
        # Return None if cancelled
        label = simpledialog.askstring(
            title="Curve label",
            prompt="Enter legend label for this curve:",
            initialvalue=default,
            parent=self
        )
        if label is None:
            return None
        label = label.strip()
        return label if label else default

    def _listbox_text(self, s: AllanSeries) -> str:
        # Display "label  |  full_path"
        return f"{s.label}  |  {str(s.path)}"

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select allan_deviation.csv (multi-select, multi-batch supported)",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not paths:
            return

        added = 0
        for p in paths:
            path = Path(p).expanduser().resolve()
            key = str(path)
            if key in self.series:
                continue

            try:
                s = read_allan_csv(path)
            except Exception as e:
                messagebox.showerror("Import failed", f"File: {path}\nError: {e}")
                continue

            default_label = self._default_label_for_path(path)
            user_label = self._prompt_label(default_label)
            if user_label is None:
                # user cancelled naming -> skip this file
                continue

            s.label = user_label
            self.series[key] = s
            self.listbox.insert(tk.END, self._listbox_text(s))
            added += 1

        self._set_status(f"Added {added} file(s). Total curves: {len(self.series)}. You can add more in batches.")

    def _selected_keys(self) -> list[str]:
        """Map selected listbox rows -> series keys by parsing the path after '|'. """
        sel = list(self.listbox.curselection())
        keys = []
        for idx in sel:
            text = self.listbox.get(idx)
            # "label  |  full_path"
            if "|" in text:
                path_str = text.split("|", 1)[1].strip()
                keys.append(str(Path(path_str)))
        return keys

    def remove_selected(self):
        sel_indices = list(self.listbox.curselection())
        if not sel_indices:
            return

        for idx in reversed(sel_indices):
            text = self.listbox.get(idx)
            self.listbox.delete(idx)
            if "|" in text:
                path_str = text.split("|", 1)[1].strip()
                self.series.pop(path_str, None)

        self._set_status(f"Removed {len(sel_indices)} file(s). Remaining: {len(self.series)}.")

    def rename_selected(self):
        keys = self._selected_keys()
        if not keys:
            messagebox.showinfo("Info", "Select one or more curves to rename.")
            return

        for key in keys:
            s = self.series.get(key)
            if s is None:
                continue
            new_label = self._prompt_label(s.label)
            if new_label is None:
                continue
            s.label = new_label

        # refresh listbox display
        self.listbox.delete(0, tk.END)
        for s in self.series.values():
            self.listbox.insert(tk.END, self._listbox_text(s))

        self._set_status("Renaming done. Click 'Plot / Refresh' to update legend.")

    def clear_all(self):
        self.listbox.delete(0, tk.END)
        self.series.clear()
        self._set_status("Cleared all curves.")

    def plot(self):
        if not self.series:
            messagebox.showinfo("Info", "Please add at least one allan_deviation.csv file.")
            return

        err_style = self.err_style.get()
        err_every = max(1, int(self.err_every.get()))

        self.ax.clear()

        # Plot each series with consistent color for line + error (bar/band)
        for s in self.series.values():
            # Draw main curve and capture line color
            (line,) = self.ax.loglog(s.tau, s.adev, marker="o", label=s.label)
            color = line.get_color()

            if err_style != "none" and s.err is not None:
                idx = np.arange(0, len(s.tau), err_every)

                if err_style == "bar":
                    # Symmetric +/- error with caps on both ends
                    # Use same color for errorbars
                    self.ax.errorbar(
                        s.tau[idx],
                        s.adev[idx],
                        yerr=s.err[idx],
                        fmt="none",
                        ecolor=color,
                        elinewidth=1.0,
                        capsize=4,      # bigger caps (horizontal bars)
                        capthick=1.0,
                        zorder=line.get_zorder() - 1,  # behind markers a bit
                    )

                elif err_style == "band":
                    # Shaded band on log axis: need strictly positive lower bound
                    # Clamp to a very small positive number to avoid log-scale invalid values
                    eps = np.min(s.adev) * 1e-6
                    lower = np.maximum(s.adev - s.err, eps)
                    upper = s.adev + s.err

                    self.ax.fill_between(
                        s.tau,
                        lower,
                        upper,
                        facecolor=color,
                        alpha=0.22,
                        linewidth=0.0,
                        zorder=line.get_zorder() - 2,
                    )

        self.ax.set_title(self.title_var.get())
        self.ax.set_xlabel(self.xlabel_var.get())
        self.ax.set_ylabel(self.ylabel_var.get())
        self.ax.grid(True, which="both", linestyle="--", linewidth=0.5)
        self.ax.legend()
        self.fig.tight_layout()
        self.canvas.draw()

        self._set_status(f"Plotted {len(self.series)} curve(s). Error mode: {err_style}, every {err_every} points.")

    def save_figure(self):
        if not self.series:
            messagebox.showinfo("Info", "Please add files and plot first, then save.")
            return

        default = "allan_compare.png"
        path = filedialog.asksaveasfilename(
            title="Save figure",
            defaultextension=".png",
            initialfile=default,
            filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg"), ("All files", "*.*")]
        )
        if not path:
            return

        out = Path(path).expanduser().resolve()
        try:
            self.fig.savefig(out, dpi=300, bbox_inches="tight")
        except Exception as e:
            messagebox.showerror("Save failed", f"{out}\nError: {e}")
            return

        self._set_status(f"Saved: {out}")


if __name__ == "__main__":
    app = AllanCompareApp()
    app.mainloop()
