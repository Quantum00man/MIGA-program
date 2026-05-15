#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Allan 方差/偏差分析工具（CSV输入：time[s], value）

功能：
1) 读取 CSV（第一列时间s，第二列数据）
2) 绘制原始数据
3) 通过一个参数 outlier_z_thresh 控制剔除异常点（MAD稳健z-score）
4) 剔除后绘制清洗后的数据
5) 计算 overlapping Allan deviation（ADEV）并绘制 log-log 图

依赖：
pip install numpy pandas matplotlib allantools
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import allantools


@dataclass
class Config:
    csv_path: str
    delimiter: str = ","
    skiprows: int = 0
    has_header: bool = True
    time_col: int = 0
    value_col: int = 1

    # 异常点剔除：稳健 z-score 阈值（越小剔除越多；越大剔除越少）
    outlier_z_thresh: float = 6.0

    # Allan 计算参数
    taus: str = "octave"  # "octave" 或者 "all"
    max_num_taus: int = 100
    # 如果时间不是严格等间隔，可以重采样到等间隔（建议 Allan 用等间隔）
    resample_to_uniform: bool = True
    # 重采样目标采样周期（秒）。None表示用中位数dt
    uniform_dt: float | None = None


def load_csv(cfg: Config) -> Tuple[np.ndarray, np.ndarray]:
    """
    读取 CSV，返回 time(s), value
    支持有/无表头；支持跳过行；支持指定分隔符。
    """
    header = 0 if cfg.has_header else None
    df = pd.read_csv(
        cfg.csv_path,
        sep=cfg.delimiter,
        header=header,
        skiprows=cfg.skiprows,
        engine="python",
    )

    # 取两列（按索引）
    t = df.iloc[:, cfg.time_col].to_numpy(dtype=float)
    x = df.iloc[:, cfg.value_col].to_numpy(dtype=float)

    # 去掉 NaN/Inf
    mask = np.isfinite(t) & np.isfinite(x)
    t, x = t[mask], x[mask]

    # 按时间排序并去重（如果有重复时间点，保留最后一个）
    order = np.argsort(t)
    t, x = t[order], x[order]
    if len(t) >= 2:
        # 去除严格重复时间
        _, idx = np.unique(t, return_index=True)
        # unique返回的是首次出现的索引，为了“保留最后一个”，用反向unique技巧
        _, idx_last = np.unique(t[::-1], return_index=True)
        idx_last = (len(t) - 1) - idx_last
        idx_last = np.sort(idx_last)
        t, x = t[idx_last], x[idx_last]

    return t, x


def robust_zscore_outlier_mask(x: np.ndarray, z_thresh: float) -> np.ndarray:
    """
    使用 MAD (Median Absolute Deviation) 的稳健 z-score 检测异常点。
    返回 mask=True 表示保留。
    robust_z = 0.6745 * (x - median) / MAD
    """
    if len(x) < 5:
        return np.ones_like(x, dtype=bool)

    med = np.median(x)
    mad = np.median(np.abs(x - med))

    if mad == 0:
        # 数据几乎常数：退化为标准差法
        std = np.std(x)
        if std == 0:
            return np.ones_like(x, dtype=bool)
        z = (x - np.mean(x)) / std
    else:
        z = 0.6745 * (x - med) / mad

    keep = np.abs(z) <= z_thresh
    return keep


def resample_uniform(t: np.ndarray, x: np.ndarray, target_dt: float | None) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    将 (t, x) 线性插值到等间隔时间网格。
    返回 (t_u, x_u, dt)
    """
    if len(t) < 2:
        raise ValueError("数据点太少，无法重采样/计算 Allan。")

    dt_med = np.median(np.diff(t))
    dt = float(target_dt) if target_dt is not None else float(dt_med)

    if dt <= 0:
        raise ValueError("时间序列 dt 非法（<=0），请检查时间列。")

    t0, t1 = t[0], t[-1]
    n = int(np.floor((t1 - t0) / dt)) + 1
    if n < 10:
        raise ValueError("重采样后点数太少，无法稳定计算 Allan。")

    t_u = t0 + dt * np.arange(n, dtype=float)
    x_u = np.interp(t_u, t, x)
    return t_u, x_u, dt


def pick_taus(n: int, dt: float, mode: str, max_num: int) -> np.ndarray:
    """
    生成 tau 列表（秒）。
    - mode="octave": 1,2,4,8,... * dt
    - mode="all": dt,2dt,3dt,... 直到 n/2
    """
    max_m = n // 2
    if max_m < 2:
        raise ValueError("数据点太少（n<4），无法计算 Allan。")

    if mode.lower() == "all":
        m = np.arange(1, max_m + 1)
    else:
        # octave
        m = []
        k = 0
        while (2 ** k) <= max_m:
            m.append(2 ** k)
            k += 1
        m = np.array(m, dtype=int)

    taus = m * dt
    if len(taus) > max_num:
        # 均匀抽样压缩 tau 数量
        idx = np.linspace(0, len(taus) - 1, max_num).round().astype(int)
        taus = taus[idx]
    return taus


def plot_time_series(t: np.ndarray, x: np.ndarray, title: str) -> None:
    plt.figure()
    plt.plot(t, x)
    plt.xlabel("Time (s)")
    plt.ylabel("Value")
    plt.title(title)
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.tight_layout()


def plot_adev(taus: np.ndarray, adev: np.ndarray, title: str) -> None:
    plt.figure()
    plt.loglog(taus, adev, marker="o")
    plt.xlabel(r"$\tau$ (s)")
    plt.ylabel("Allan Deviation")
    plt.title(title)
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.tight_layout()


def main():
    ap = argparse.ArgumentParser(description="从CSV计算 Allan 方差/偏差（含异常点剔除与绘图）")
    ap.add_argument("csv", help="CSV 文件路径（第一列时间s，第二列数据）")
    ap.add_argument("--delimiter", default=",", help="CSV 分隔符，默认逗号','；制表符用 '\\t'")
    ap.add_argument("--skiprows", type=int, default=0, help="跳过文件开头行数")
    ap.add_argument("--no-header", action="store_true", help="CSV 没有表头（默认认为有表头）")
    ap.add_argument("--time-col", type=int, default=0, help="时间列索引（从0开始），默认0")
    ap.add_argument("--value-col", type=int, default=1, help="数据列索引（从0开始），默认1")

    # 一个参数控制剔除强度
    ap.add_argument("--outlier-z", type=float, default=6.0,
                    help="异常点剔除阈值（稳健z-score，默认6.0；越小剔除越多）")

    ap.add_argument("--taus", choices=["octave", "all"], default="octave", help="tau 取样方式")
    ap.add_argument("--max-taus", type=int, default=100, help="最多 tau 点数（默认100）")
    ap.add_argument("--no-resample", action="store_true", help="不重采样到等间隔（不推荐）")
    ap.add_argument("--dt", type=float, default=None, help="重采样目标 dt（秒），默认使用时间差中位数")

    args = ap.parse_args()

    cfg = Config(
        csv_path=args.csv,
        delimiter=args.delimiter,
        skiprows=args.skiprows,
        has_header=(not args.no_header),
        time_col=args.time_col,
        value_col=args.value_col,
        outlier_z_thresh=args.outlier_z,
        taus=args.taus,
        max_num_taus=args.max_taus,
        resample_to_uniform=(not args.no_resample),
        uniform_dt=args.dt,
    )

    # 1) 读取
    t, x = load_csv(cfg)
    if len(t) < 5:
        raise SystemExit("数据点太少，至少需要5个点。")

    # 2) 原始图
    plot_time_series(t, x, f"Raw Data (N={len(x)})")

    # 3) 异常点剔除（一个参数控制：outlier_z_thresh）
    keep = robust_zscore_outlier_mask(x, cfg.outlier_z_thresh)
    t2, x2 = t[keep], x[keep]

    # 画“保留/剔除”对比（可视化哪个点被剔除）
    plt.figure()
    plt.plot(t, x, label="raw")
    plt.plot(t2, x2, ".", label=f"kept (z<={cfg.outlier_z_thresh:g})")
    plt.xlabel("Time (s)")
    plt.ylabel("Value")
    plt.title(f"Outlier Removal: kept {len(x2)}/{len(x)}")
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.legend()
    plt.tight_layout()

    # 4) 清洗后图
    plot_time_series(t2, x2, f"Cleaned Data (N={len(x2)})")

    if len(t2) < 10:
        raise SystemExit("剔除后数据点太少（<10），请调大 --outlier-z 或检查数据。")

    # 5) 重采样到等间隔（推荐）
    if cfg.resample_to_uniform:
        t_u, x_u, dt = resample_uniform(t2, x2, cfg.uniform_dt)
    else:
        # 不重采样：用 median(dt) 作为 rate 的近似（但 Allan 更推荐严格等间隔）
        dt = float(np.median(np.diff(t2)))
        t_u, x_u = t2, x2

    # 6) 生成 tau
    taus = pick_taus(len(x_u), dt, cfg.taus, cfg.max_num_taus)

    # 7) 计算 overlapping Allan deviation（ADEV）
    # allantools 里 adev 输入通常是等间隔采样序列，rate=1/dt
    rate = 1.0 / dt
    taus_out, adev, adev_err, ns = allantools.oadev(x_u, rate=rate, taus=taus)

    # 8) 画 Allan 偏差图（log-log）
    plot_adev(taus_out, adev, "Overlapping Allan Deviation (OADEV)")

    print("=== Summary ===")
    print(f"Raw points:     {len(x)}")
    print(f"Kept points:    {len(x2)} (outlier_z_thresh={cfg.outlier_z_thresh})")
    print(f"Uniform points: {len(x_u)} (dt={dt:.6g}s, rate={rate:.6g}Hz)")
    print(f"Tau count:      {len(taus_out)}")
    print("Done. Close the figures to exit.")

    plt.show()


if __name__ == "__main__":
    main()
