#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Allan deviation 多组对比绘图 GUI（Windows/Linux 通用）
- 通过按钮选择一个或多个 allan_deviation.csv（可多次添加/分次上传多组）
- 叠加绘制 Allan deviation（log-log）
- 支持误差：bar（误差棒）/ band（阴影带）/ none
- 曲线 label 默认用 CSV 文件名；可选改为父目录名（例如 results_xxx）
- 可保存图片（png/pdf/svg）

CSV 至少需要列：
- tau_s
- allan_deviation
可选列：
- allan_error
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


@dataclass
class AllanSeries:
    path: Path
    tau: np.ndarray
    adev: np.ndarray
    err: Optional[np.ndarray]


def read_allan_csv(path: Path) -> AllanSeries:
    df = pd.read_csv(path)

    required = {"tau_s", "allan_deviation"}
    if not required.issubset(df.columns):
        raise ValueError(
            f"缺少必要列 {required}，当前列为：{list(df.columns)}"
        )

    tau = df["tau_s"].to_numpy(dtype=float)
    adev = df["allan_deviation"].to_numpy(dtype=float)
    err = df["allan_error"].to_numpy(dtype=float) if "allan_error" in df.columns else None

    # 清洗：tau>0, adev>0
    mask = np.isfinite(tau) & np.isfinite(adev) & (tau > 0) & (adev > 0)
    if err is not None:
        mask = mask & np.isfinite(err) & (err >= 0)

    tau, adev = tau[mask], adev[mask]
    if err is not None:
        err = err[mask]

    if len(tau) < 2:
        raise ValueError("有效数据点太少（<2）。")

    # 按 tau 排序
    order = np.argsort(tau)
    tau, adev = tau[order], adev[order]
    if err is not None:
        err = err[order]

    return AllanSeries(path=path, tau=tau, adev=adev, err=err)


class AllanCompareApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Allan Deviation Compare (GUI)")
        self.geometry("1100x700")

        # key 用绝对路径字符串，避免重名覆盖
        self.series: Dict[str, AllanSeries] = {}

        self._build_ui()

    def _build_ui(self):
        # 主布局：左侧控制 + 右侧绘图
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

        # ---------- 左侧：文件列表与控制 ----------
        ttk.Label(left, text="已导入的 Allan 文件：").grid(row=0, column=0, sticky="w")

        self.listbox = tk.Listbox(left, width=52, height=18, selectmode=tk.EXTENDED)
        self.listbox.grid(row=1, column=0, sticky="nsew", pady=(6, 6))

        btns = ttk.Frame(left)
        btns.grid(row=2, column=0, sticky="ew")
        btns.columnconfigure((0, 1, 2), weight=1)

        ttk.Button(btns, text="添加文件…", command=self.add_files).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="移除选中", command=self.remove_selected).grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="清空", command=self.clear_all).grid(row=0, column=2, sticky="ew")

        # 选项
        opts = ttk.LabelFrame(left, text="绘图选项", padding=10)
        opts.grid(row=3, column=0, sticky="ew", pady=(10, 10))
        opts.columnconfigure(1, weight=1)

        ttk.Label(opts, text="误差显示：").grid(row=0, column=0, sticky="w")
        self.err_style = tk.StringVar(value="bar")
        ttk.Combobox(
            opts, textvariable=self.err_style,
            values=["bar", "band", "none"], state="readonly", width=10
        ).grid(row=0, column=1, sticky="w", padx=(6, 0))

        ttk.Label(opts, text="误差抽样间隔：").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.err_every = tk.IntVar(value=3)
        ttk.Spinbox(opts, from_=1, to=200, textvariable=self.err_every, width=10).grid(
            row=1, column=1, sticky="w", padx=(6, 0), pady=(8, 0)
        )

        self.use_parent_as_label = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opts, text="图例用父目录名（results_xxx）",
            variable=self.use_parent_as_label
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        # 标题/轴标签
        labels = ttk.LabelFrame(left, text="标题与轴标签", padding=10)
        labels.grid(row=4, column=0, sticky="ew")
        labels.columnconfigure(1, weight=1)

        self.title_var = tk.StringVar(value="Allan Deviation Comparison")
        self.xlabel_var = tk.StringVar(value=r"$\tau$ (s)")
        self.ylabel_var = tk.StringVar(value="Allan Deviation")

        ttk.Label(labels, text="标题：").grid(row=0, column=0, sticky="w")
        ttk.Entry(labels, textvariable=self.title_var, width=42).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        ttk.Label(labels, text="X轴：").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(labels, textvariable=self.xlabel_var, width=42).grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))

        ttk.Label(labels, text="Y轴：").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(labels, textvariable=self.ylabel_var, width=42).grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))

        # 操作按钮
        actions = ttk.Frame(left)
        actions.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        actions.columnconfigure((0, 1), weight=1)

        ttk.Button(actions, text="绘图 / 刷新", command=self.plot).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="保存图片…", command=self.save_figure).grid(row=0, column=1, sticky="ew")

        # 状态栏
        self.status = tk.StringVar(value="就绪。点击“添加文件…”导入 allan_deviation.csv（可多次添加）。")
        ttk.Label(left, textvariable=self.status, foreground="#444").grid(row=7, column=0, sticky="w", pady=(10, 0))

        # ---------- 右侧：Matplotlib（关键：不要在同一容器混用 grid/pack） ----------
        plot_frame = ttk.Frame(right)
        plot_frame.grid(row=0, column=0, sticky="nsew")
        plot_frame.rowconfigure(0, weight=1)
        plot_frame.columnconfigure(0, weight=1)

        toolbar_frame = ttk.Frame(right)
        toolbar_frame.grid(row=1, column=0, sticky="ew")

        # Figure / Axes
        self.fig = Figure(figsize=(7, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)

        # Canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        # Toolbar（注意：toolbar 内部使用 pack，但它 pack 在 toolbar_frame 里，不会与 plot_frame 的 grid 冲突）
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()

    def _set_status(self, text: str):
        self.status.set(text)

    def _label_for_path(self, p: Path) -> str:
        if self.use_parent_as_label.get():
            return p.parent.name if p.parent.name else p.name
        return p.name

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="选择 allan_deviation.csv（可多选，可分次添加）",
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
                messagebox.showerror("导入失败", f"文件：{path}\n错误：{e}")
                continue

            self.series[key] = s
            self.listbox.insert(tk.END, key)
            added += 1

        self._set_status(f"已添加 {added} 个文件（总计 {len(self.series)}）。可继续点击“添加文件…”分次导入。")

    def remove_selected(self):
        sel = list(self.listbox.curselection())
        if not sel:
            return

        for idx in reversed(sel):
            key = self.listbox.get(idx)
            self.listbox.delete(idx)
            self.series.pop(key, None)

        self._set_status(f"已移除 {len(sel)} 个文件（剩余 {len(self.series)}）。")

    def clear_all(self):
        self.listbox.delete(0, tk.END)
        self.series.clear()
        self._set_status("已清空。")

    def plot(self):
        if not self.series:
            messagebox.showinfo("提示", "请先添加至少一个 allan_deviation.csv")
            return

        err_style = self.err_style.get()
        err_every = max(1, int(self.err_every.get()))

        self.ax.clear()

        # 绘制多组数据
        for key, s in self.series.items():
            label = self._label_for_path(s.path)
            self.ax.loglog(s.tau, s.adev, marker="o", label=label)

            if err_style != "none" and s.err is not None:
                idx = np.arange(0, len(s.tau), err_every)

                if err_style == "bar":
                    self.ax.errorbar(
                        s.tau[idx],
                        s.adev[idx],
                        yerr=s.err[idx],
                        fmt="none",
                        capsize=2,
                    )
                elif err_style == "band":
                    # band：adev ± err，log坐标下下限需 > 0
                    eps = np.min(s.adev[s.adev > 0]) * 1e-6
                    lower = np.maximum(s.adev - s.err, eps)
                    upper = s.adev + s.err
                    self.ax.fill_between(s.tau, lower, upper, alpha=0.2)

        self.ax.set_title(self.title_var.get())
        self.ax.set_xlabel(self.xlabel_var.get())
        self.ax.set_ylabel(self.ylabel_var.get())
        self.ax.grid(True, which="both", linestyle="--", linewidth=0.5)
        self.ax.legend()
        self.fig.tight_layout()
        self.canvas.draw()

        self._set_status(f"已绘图：{len(self.series)} 条曲线（误差：{err_style}，每 {err_every} 点显示一次）。")

    def save_figure(self):
        if not self.series:
            messagebox.showinfo("提示", "请先添加文件并绘图，再保存图片。")
            return

        default = "allan_compare.png"
        path = filedialog.asksaveasfilename(
            title="保存图片",
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
            messagebox.showerror("保存失败", f"{out}\n错误：{e}")
            return

        self._set_status(f"已保存：{out}")


if __name__ == "__main__":
    app = AllanCompareApp()
    app.mainloop()
