#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Allan 稳定度分析工具（CSV: time[s], value）
- 读入 CSV（第1列时间s，第2列数据）
- 绘制 Fig1 原始数据
- 通过一个参数 --outlier-z（MAD稳健z-score）剔除明显错误点（Fig2 对比）
- 绘制 Fig3 清洗后数据
- 重采样到等间隔（推荐）
- 计算相对偏差 y(t)=(x-mean)/mean（Fig4）
- 对 y(t) 计算 Overlapping Allan Deviation（Fig5）
- 可选：--save 保存 Fig1-5 图片 + 对应数据 + summary.txt 到本地目录

依赖：
pip install numpy pandas matplotlib allantools
launch (win)

mkdir -p ~/.venvs
python3 -m venv ~/.venvs/allen

launch(linux)
first_run:
mkdir -p ~/.venvs
python3 -m venv ~/.venvs/allen
source ~/.venvs/allen/bin/activate
python -m pip install -U pip
python -m pip install numpy pandas matplotlib allantools
----------------------------------------------------



--run--
source ~/.venvs/allen/bin/activate
python allen_toolv3.py analysis_xx_runxx_allan.csv --outlier-z 6 --save

"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
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

    # 异常点剔除强度（唯一控制参数：越小剔除越多）
    outlier_z_thresh: float = 6.0

    # Allan 参数
    taus_mode: str = "octave"  # "octave" 或 "all"
    max_num_taus: int = 100

    # 重采样
    resample_to_uniform: bool = True
    uniform_dt: float | None = None  # None -> 使用时间差中位数


def load_csv(cfg: Config) -> Tuple[np.ndarray, np.ndarray]:
    """读取 CSV -> (t, x)，并进行基本清洗/排序/去重。"""
    header = 0 if cfg.has_header else None
    df = pd.read_csv(
        cfg.csv_path,
        sep=cfg.delimiter,
        header=header,
        skiprows=cfg.skiprows,
        engine="python",
    )

    t = df.iloc[:, cfg.time_col].to_numpy(dtype=float)
    x = df.iloc[:, cfg.value_col].to_numpy(dtype=float)

    mask = np.isfinite(t) & np.isfinite(x)
    t, x = t[mask], x[mask]

    order = np.argsort(t)
    t, x = t[order], x[order]

    # 去重时间（保留最后一个）
    if len(t) >= 2:
        _, idx_last = np.unique(t[::-1], return_index=True)
        idx_last = (len(t) - 1) - idx_last
        idx_last = np.sort(idx_last)
        t, x = t[idx_last], x[idx_last]

    return t, x


def robust_zscore_outlier_mask(x: np.ndarray, z_thresh: float) -> np.ndarray:
    """
    MAD稳健z-score：abs(z) > z_thresh -> 异常点剔除
    robust_z = 0.6745 * (x - median) / MAD
    返回 keep mask（True=保留）。
    """
    if len(x) < 5:
        return np.ones_like(x, dtype=bool)

    med = np.median(x)
    mad = np.median(np.abs(x - med))

    if mad == 0:
        std = np.std(x)
        if std == 0:
            return np.ones_like(x, dtype=bool)
        z = (x - np.mean(x)) / std
    else:
        z = 0.6745 * (x - med) / mad

    return np.abs(z) <= z_thresh


def resample_uniform(t: np.ndarray, x: np.ndarray, target_dt: float | None) -> Tuple[np.ndarray, np.ndarray, float]:
    """线性插值重采样到等间隔时间网格。"""
    if len(t) < 2:
        raise ValueError("数据点太少，无法重采样。")

    dt_med = float(np.median(np.diff(t)))
    dt = float(target_dt) if target_dt is not None else dt_med
    if dt <= 0:
        raise ValueError("dt <= 0，请检查时间列。")

    t0, t1 = float(t[0]), float(t[-1])
    n = int(np.floor((t1 - t0) / dt)) + 1
    if n < 10:
        raise ValueError("重采样后点数太少，无法稳定计算 Allan。")

    t_u = t0 + dt * np.arange(n, dtype=float)
    x_u = np.interp(t_u, t, x)
    return t_u, x_u, dt


def pick_taus(n: int, dt: float, mode: str, max_num: int) -> np.ndarray:
    """生成 tau 列表（秒）。"""
    max_m = n // 2
    if max_m < 2:
        raise ValueError("数据点太少（n<4），无法计算 Allan。")

    mode = mode.lower()
    if mode == "all":
        m = np.arange(1, max_m + 1, dtype=int)
    else:
        # octave: 1,2,4,8,...
        ms = []
        k = 0
        while (2**k) <= max_m:
            ms.append(2**k)
            k += 1
        m = np.array(ms, dtype=int)

    taus = m * dt
    if len(taus) > max_num:
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


def plot_outlier_overlay(t: np.ndarray, x: np.ndarray, keep: np.ndarray, zth: float) -> None:
    plt.figure()
    plt.plot(t, x, label="raw")
    plt.plot(t[keep], x[keep], ".", label=f"kept (|z|≤{zth:g})")
    plt.xlabel("Time (s)")
    plt.ylabel("Value")
    plt.title(f"Outlier removal: kept {keep.sum()}/{len(keep)}")
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.legend()
    plt.tight_layout()


def plot_adev(taus: np.ndarray, adev: np.ndarray, title: str, ylabel: str) -> None:
    plt.figure()
    plt.loglog(taus, adev, marker="o")
    plt.xlabel(r"$\tau$ (s)")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.tight_layout()


def save_current_figure(save_dir: Path | None, filename: str) -> None:
    """保存当前 figure（plt.gcf()）"""
    if save_dir is None:
        return
    plt.savefig(save_dir / filename, dpi=300, bbox_inches="tight")


def save_df(save_dir: Path | None, filename: str, df: pd.DataFrame) -> None:
    if save_dir is None:
        return
    df.to_csv(save_dir / filename, index=False)


def main():
    ap = argparse.ArgumentParser(description="从CSV计算（相对偏差）Allan稳定度，含异常点剔除与绘图/保存")
    ap.add_argument("csv", help="CSV 文件路径（第一列时间s，第二列数据）")
    ap.add_argument("--delimiter", default=",", help="分隔符，默认','；制表符用 '\\t'")
    ap.add_argument("--skiprows", type=int, default=0, help="跳过开头行数")
    ap.add_argument("--no-header", action="store_true", help="CSV 无表头（默认有表头）")
    ap.add_argument("--time-col", type=int, default=0, help="时间列索引（从0开始）")
    ap.add_argument("--value-col", type=int, default=1, help="数据列索引（从0开始）")

    # 你要的“一个参数控制剔除”
    ap.add_argument("--outlier-z", type=float, default=6.0,
                    help="异常点剔除阈值（MAD稳健z-score），越小剔除越多，默认6.0")

    ap.add_argument("--taus", choices=["octave", "all"], default="octave", help="tau 取样方式")
    ap.add_argument("--max-taus", type=int, default=100, help="最多 tau 点数")
    ap.add_argument("--no-resample", action="store_true", help="不重采样到等间隔（不推荐）")
    ap.add_argument("--dt", type=float, default=None, help="重采样目标 dt（秒），默认用时间差中位数")

    ap.add_argument("--save", action="store_true",
                    help="Save Fig1-5 images and corresponding data to local directory")

    args = ap.parse_args()

    cfg = Config(
        csv_path=args.csv,
        delimiter=args.delimiter,
        skiprows=args.skiprows,
        has_header=(not args.no_header),
        time_col=args.time_col,
        value_col=args.value_col,
        outlier_z_thresh=args.outlier_z,
        taus_mode=args.taus,
        max_num_taus=args.max_taus,
        resample_to_uniform=(not args.no_resample),
        uniform_dt=args.dt,
    )

    # 保存目录
    save_dir: Path | None = None
    if args.save:
        base = Path(cfg.csv_path).stem
        save_dir = Path(f"results_{base}")
        save_dir.mkdir(parents=True, exist_ok=True)

    # 1) 读入
    t, x = load_csv(cfg)
    if len(x) < 10:
        raise SystemExit("数据点太少（<10），无法稳定分析。")

    # Fig1: 原始数据
    plot_time_series(t, x, f"Raw Data (N={len(x)})")
    save_current_figure(save_dir, "fig1_raw_data.png")
    save_df(save_dir, "raw_data.csv", pd.DataFrame({"time_s": t, "value": x}))

    # 2) 异常点剔除（在原始量 x 上做稳健剔除）
    keep = robust_zscore_outlier_mask(x, cfg.outlier_z_thresh)

    # Fig2: 剔除对比
    plot_outlier_overlay(t, x, keep, cfg.outlier_z_thresh)
    save_current_figure(save_dir, "fig2_outlier_overlay.png")
    # 保存 mask 方便追溯
    save_df(save_dir, "outlier_mask.csv",
            pd.DataFrame({"time_s": t, "value": x, "kept": keep.astype(int)}))

    t2, x2 = t[keep], x[keep]

    # Fig3: 清洗后数据
    plot_time_series(t2, x2, f"Cleaned Data (N={len(x2)})")
    save_current_figure(save_dir, "fig3_cleaned_data.png")
    save_df(save_dir, "cleaned_data.csv", pd.DataFrame({"time_s": t2, "value": x2}))

    if len(x2) < 10:
        raise SystemExit("剔除后数据点太少（<10），请调大 --outlier-z 或检查数据。")

    # 3) 重采样（推荐）
    if cfg.resample_to_uniform:
        t_u, x_u, dt = resample_uniform(t2, x2, cfg.uniform_dt)
    else:
        dt = float(np.median(np.diff(t2)))
        t_u, x_u = t2, x2

    rate = 1.0 / dt

    # 4) 相对偏差 y = (x - mean) / mean
    mu = float(np.mean(x_u))
    if np.isclose(mu, 0.0, atol=0.0, rtol=1e-12):
        raise SystemExit(
            "均值接近 0，无法做相对偏差归一化（会放大噪声/失真）。"
            "请改用绝对 Allan，或对数据做基线平移/换量纲。"
        )
    y = (x_u - mu) / mu

    # Fig4: 相对偏差时间序列
    plot_time_series(t_u, y, "Relative Deviation y(t) = (x - mean)/mean")
    save_current_figure(save_dir, "fig4_relative_deviation.png")
    save_df(save_dir, "relative_deviation.csv",
            pd.DataFrame({"time_s": t_u, "relative_deviation": y}))
    # 同时保存重采样后的绝对数据（可复现）
    save_df(save_dir, "uniform_resampled.csv",
            pd.DataFrame({"time_s": t_u, "value": x_u}))

    # 5) Allan (OADEV) on y(t)
    taus = pick_taus(len(y), dt, cfg.taus_mode, cfg.max_num_taus)
    taus_out, adev, adev_err, ns = allantools.oadev(y, rate=rate, taus=taus)

    # Fig5: Allan 偏差（相对）
    plot_adev(
        taus_out,
        adev,
        title="Overlapping Allan Deviation (Fractional / Relative)",
        ylabel="Fractional Allan Deviation",
    )
    save_current_figure(save_dir, "fig5_allan_deviation.png")

    # 保存 Allan 数据
    save_df(save_dir, "allan_deviation.csv", pd.DataFrame({
        "tau_s": taus_out,
        "allan_deviation": adev,
        "allan_error": adev_err,
        "num_pairs": ns,
    }))

    # summary
    if save_dir is not None:
        summary = (
            "Allan Stability Analysis Summary\n"
            + "=" * 40 + "\n"
            + f"Input file: {cfg.csv_path}\n"
            + f"Delimiter: {cfg.delimiter!r}, skiprows={cfg.skiprows}, header={cfg.has_header}\n"
            + f"Columns: time_col={cfg.time_col}, value_col={cfg.value_col}\n"
            + f"Outlier z-threshold (MAD): {cfg.outlier_z_thresh}\n"
            + f"Points (raw/kept): {len(x)} / {len(x2)}\n"
            + f"Resample to uniform: {cfg.resample_to_uniform}\n"
            + f"Uniform dt (s): {dt:.12g}\n"
            + f"Rate (Hz): {rate:.12g}\n"
            + f"Uniform points: {len(x_u)}\n"
            + f"Mean after cleaning (uniform): {mu:.12g}\n"
            + f"Taus mode: {cfg.taus_mode}, max_num_taus={cfg.max_num_taus}\n"
            + f"Tau count: {len(taus_out)}\n"
        )
        (save_dir / "summary.txt").write_text(summary, encoding="utf-8")

    print("=== Summary ===")
    print(f"Raw points:        {len(x)}")
    print(f"Kept points:       {len(x2)} (outlier_z_thresh={cfg.outlier_z_thresh})")
    print(f"Uniform points:    {len(x_u)} (dt={dt:.6g}s, rate={rate:.6g}Hz)")
    print(f"Mean after clean:  {mu:.6g}")
    print(f"Tau count:         {len(taus_out)}")
    if save_dir is not None:
        print(f"Saved to directory: {save_dir.resolve()}")
    print("Done. Close figures to exit.")

    plt.show()


if __name__ == "__main__":
    main()
