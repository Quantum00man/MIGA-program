from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import numpy as np
from matplotlib.figure import Figure
from scipy import signal

UNIFORMITY_TOLERANCE = 1e-2
MIN_SAMPLES_FOR_PSD = 32
MAX_PLOT_POINTS = 20000
DEFAULT_IMPEDANCE_OHM = 50.0
DEFAULT_PEAK_COUNT = 5
DEFAULT_PEAK_PROMINENCE_DB = 6.0

DISPLAY_UNIT_V2_PER_HZ = "v2_per_hz"
DISPLAY_UNIT_DBV_PER_SQRT_HZ = "dbv_per_sqrt_hz"
DISPLAY_UNIT_DBM_PER_HZ = "dbm_per_hz"
DISPLAY_UNIT_CHOICES = (
    DISPLAY_UNIT_V2_PER_HZ,
    DISPLAY_UNIT_DBV_PER_SQRT_HZ,
    DISPLAY_UNIT_DBM_PER_HZ,
)
DISPLAY_UNIT_LABELS = {
    DISPLAY_UNIT_V2_PER_HZ: "V^2/Hz",
    DISPLAY_UNIT_DBV_PER_SQRT_HZ: "dBV/√Hz",
    DISPLAY_UNIT_DBM_PER_HZ: "dBm/Hz",
}
DISPLAY_UNIT_EXPORT_COLUMNS = {
    DISPLAY_UNIT_V2_PER_HZ: "psd_v2_per_hz",
    DISPLAY_UNIT_DBV_PER_SQRT_HZ: "asd_dbv_per_sqrt_hz",
    DISPLAY_UNIT_DBM_PER_HZ: "psd_dbm_per_hz",
}
AXIS_SCALE_LINEAR = "linear"
AXIS_SCALE_LOG = "log"
AXIS_SCALE_CHOICES = (AXIS_SCALE_LINEAR, AXIS_SCALE_LOG)
AXIS_SCALE_LABELS = {
    AXIS_SCALE_LINEAR: "Linear",
    AXIS_SCALE_LOG: "Log",
}

DetrendType = Union[str, bool]


@dataclass(frozen=True)
class RawSignalData:
    """Raw signal loaded from CSV before time-axis correction."""

    time: np.ndarray
    voltage: np.ndarray


@dataclass(frozen=True)
class SignalData:
    """Uniformly sampled signal used for PSD estimation."""

    time: np.ndarray
    voltage: np.ndarray
    dt: float
    fs: float


@dataclass(frozen=True)
class PSDAnalysisResult:
    """Container for PSD analysis results and metadata."""

    raw: RawSignalData
    processed: SignalData
    frequency: np.ndarray
    psd: np.ndarray
    nperseg: int
    noverlap: int
    window: str
    detrend: DetrendType
    preprocess_method: str
    preprocess_details: str


@dataclass(frozen=True)
class PSDPeak:
    """Detected PSD peak."""

    frequency_hz: float
    psd_v2_per_hz: float
    prominence_db: float


def load_signal_csv(csv_path: Path) -> RawSignalData:
    """
    Load a two-column CSV signal file.

    Expected format:
    1. First row: header.
    2. First column: time in seconds.
    3. Second column: voltage in volts.
    """

    if not csv_path.exists():
        raise FileNotFoundError(f"未找到文件: {csv_path}")

    raw = np.genfromtxt(csv_path, delimiter=",", skip_header=1, dtype=float)

    if raw.size == 0:
        raise ValueError("CSV 文件为空，或除表头外没有可用数据。")

    if raw.ndim == 1:
        raw = raw.reshape(1, -1)

    raw = raw[~np.all(np.isnan(raw), axis=1)]
    if raw.size == 0:
        raise ValueError("CSV 中没有有效数据行。")

    if raw.shape[1] < 2:
        raise ValueError("CSV 至少需要两列：时间(s) 和电压(V)。")

    time = np.asarray(raw[:, 0], dtype=float)
    voltage = np.asarray(raw[:, 1], dtype=float)

    if np.any(~np.isfinite(time)) or np.any(~np.isfinite(voltage)):
        raise ValueError("时间列或电压列包含 NaN / Inf，请先清洗数据。")

    if time.size < 2:
        raise ValueError("至少需要 2 个采样点才能估计采样间隔。")

    return RawSignalData(time=time, voltage=voltage)


def validate_uniform_sampling(time: np.ndarray) -> float:
    """Validate that the time axis is strictly increasing and nearly uniform."""

    dt = np.diff(time)

    if np.any(dt <= 0.0):
        raise ValueError("时间列必须严格递增。")

    median_dt = float(np.median(dt))
    if median_dt <= 0.0:
        raise ValueError("检测到非正采样间隔，无法计算采样频率。")

    relative_spread = float(np.max(np.abs(dt - median_dt)) / median_dt)
    if relative_spread > UNIFORMITY_TOLERANCE:
        raise ValueError(
            "Welch PSD 需要近似等间隔采样。检测到时间步长波动超过 1%，"
            "请先将数据重采样为等间隔时间序列。"
        )

    return median_dt


def summarize_time_runs(time: np.ndarray) -> tuple[int, int, int]:
    """Return the number of repeated timestamp runs and their min/max lengths."""

    if time.size == 0:
        return 0, 0, 0

    change_points = np.flatnonzero(np.diff(time) != 0.0) + 1
    starts = np.concatenate(([0], change_points))
    ends = np.concatenate((change_points, [time.size]))
    run_lengths = ends - starts
    repeated_runs = int(np.sum(run_lengths > 1))
    return repeated_runs, int(np.min(run_lengths)), int(np.max(run_lengths))


def reconstruct_uniform_time_axis(data: RawSignalData) -> SignalData:
    """
    Reconstruct a uniform time axis from the record endpoints and sample count.

    This is intended for CSV exports where the textual time column has limited
    precision and therefore contains repeated timestamps despite an underlying
    uniformly sampled acquisition.
    """

    if data.time.size < 2:
        raise ValueError("至少需要 2 个采样点才能重建时间轴。")

    t_start = float(data.time[0])
    t_stop = float(data.time[-1])
    if not np.isfinite(t_start) or not np.isfinite(t_stop):
        raise ValueError("时间列起点或终点不是有限数值。")
    if t_stop <= t_start:
        raise ValueError("时间列首末值无法定义正的采样间隔。")

    reconstructed_time = np.linspace(t_start, t_stop, data.time.size, dtype=float)
    dt = float(reconstructed_time[1] - reconstructed_time[0])
    if dt <= 0.0:
        raise ValueError("重建后的采样间隔非正，无法继续。")

    return SignalData(
        time=reconstructed_time,
        voltage=data.voltage.copy(),
        dt=dt,
        fs=1.0 / dt,
    )


def prepare_signal(data: RawSignalData) -> tuple[SignalData, str, str]:
    """Prepare a uniformly sampled signal for PSD estimation."""

    if data.time.size < MIN_SAMPLES_FOR_PSD:
        raise ValueError(
            f"样本数过少（{data.time.size}），少于 {MIN_SAMPLES_FOR_PSD}，无法稳定估计 PSD。"
        )

    try:
        dt = validate_uniform_sampling(data.time)
    except ValueError:
        processed = reconstruct_uniform_time_axis(data)
        repeated_runs, min_run, max_run = summarize_time_runs(data.time)
        details = (
            "原始时间列存在重复时间戳或非均匀步长，因此按首末时间和总样本数"
            "重建了均匀时间轴。"
        )
        if repeated_runs > 0:
            details += (
                f" 检测到 {repeated_runs} 个重复时间块，"
                f"重复块长度范围为 {min_run} 到 {max_run} 行。"
            )
        return processed, "reconstructed_uniform_time_axis", details

    processed = SignalData(
        time=data.time.copy(),
        voltage=data.voltage.copy(),
        dt=dt,
        fs=1.0 / dt,
    )
    details = "原始时间列已满足严格递增且近似等间隔，直接用于 PSD 计算。"
    return processed, "use_raw_time_axis", details


def suggest_nperseg(n_samples: int) -> int:
    """
    Suggest a Welch segment length.

    Strategy:
    - Aim for about four segments across the record.
    - Use a power of two for efficient FFT computation.
    - Keep the value within practical bounds for stable estimates.
    """

    if n_samples < MIN_SAMPLES_FOR_PSD:
        raise ValueError(
            f"样本数过少（{n_samples}），无法稳定估计 PSD。"
        )

    target = max(MIN_SAMPLES_FOR_PSD, n_samples // 4)
    nperseg = 2 ** int(np.floor(np.log2(target)))
    nperseg = int(min(nperseg, n_samples))

    if nperseg < MIN_SAMPLES_FOR_PSD:
        nperseg = MIN_SAMPLES_FOR_PSD

    return nperseg


def resolve_nperseg(n_samples: int, nperseg: Optional[int]) -> int:
    """Resolve user-provided or automatic `nperseg`."""

    if nperseg is None:
        return suggest_nperseg(n_samples)

    if nperseg < MIN_SAMPLES_FOR_PSD:
        raise ValueError(
            f"nperseg 不能小于 {MIN_SAMPLES_FOR_PSD}。"
        )

    if nperseg > n_samples:
        raise ValueError(
            f"nperseg={nperseg} 大于时间轴校正后的样本数 {n_samples}。"
        )

    return int(nperseg)


def normalize_detrend(value: str) -> DetrendType:
    """Normalize detrend selection."""

    normalized = value.strip().lower()
    if normalized == "none":
        return False
    if normalized in {"constant", "linear"}:
        return normalized
    raise ValueError("detrend 仅支持: constant, linear, none。")


def normalize_display_unit(value: str) -> str:
    """Normalize display unit identifiers from GUI labels or CLI choices."""

    normalized = value.strip()
    if normalized in DISPLAY_UNIT_CHOICES:
        return normalized

    for unit_id, label in DISPLAY_UNIT_LABELS.items():
        if normalized == label:
            return unit_id

    raise ValueError(
        "纵坐标单位仅支持: "
        + ", ".join(DISPLAY_UNIT_LABELS[unit] for unit in DISPLAY_UNIT_CHOICES)
    )


def validate_impedance_ohm(value: float) -> float:
    """Validate reference impedance used for dBm conversion."""

    if not np.isfinite(value) or value <= 0.0:
        raise ValueError("参考阻抗必须是正数。")
    return float(value)


def normalize_axis_scale(value: str) -> str:
    """Normalize axis scale identifiers from GUI labels or CLI choices."""

    normalized = value.strip().lower()
    if normalized in AXIS_SCALE_CHOICES:
        return normalized

    for scale_id, label in AXIS_SCALE_LABELS.items():
        if normalized == label.lower():
            return scale_id

    raise ValueError("坐标轴比例仅支持: linear, log。")


def resolve_psd_axis_scales(
    display_unit: str,
    x_scale: Optional[str] = None,
    y_scale: Optional[str] = None,
) -> tuple[str, str]:
    """Resolve and validate PSD axis scales for the selected display unit."""

    normalized_display_unit = normalize_display_unit(display_unit)
    resolved_x_scale = AXIS_SCALE_LINEAR if x_scale is None else normalize_axis_scale(x_scale)

    if y_scale is None:
        resolved_y_scale = (
            AXIS_SCALE_LOG
            if normalized_display_unit == DISPLAY_UNIT_V2_PER_HZ
            else AXIS_SCALE_LINEAR
        )
    else:
        resolved_y_scale = normalize_axis_scale(y_scale)

    if (
        normalized_display_unit != DISPLAY_UNIT_V2_PER_HZ
        and resolved_y_scale == AXIS_SCALE_LOG
    ):
        raise ValueError(
            "dBV/√Hz 和 dBm/Hz 已经是对数量显示，纵轴请使用 linear。"
        )

    return resolved_x_scale, resolved_y_scale


def validate_peak_count(value: int) -> int:
    """Validate the requested number of reported peaks."""

    if value < 1:
        raise ValueError("峰值数量必须为正整数。")
    return int(value)


def validate_peak_prominence_db(value: float) -> float:
    """Validate minimum peak prominence in dB."""

    if not np.isfinite(value) or value < 0.0:
        raise ValueError("峰值 prominence 必须是大于等于 0 的数值（单位 dB）。")
    return float(value)


def detect_psd_peaks(
    frequency_hz: np.ndarray,
    psd_v2_per_hz: np.ndarray,
    peak_count: int = DEFAULT_PEAK_COUNT,
    prominence_db: float = DEFAULT_PEAK_PROMINENCE_DB,
) -> list[PSDPeak]:
    """Detect dominant PSD peaks on a dB-transformed spectrum."""

    resolved_peak_count = validate_peak_count(peak_count)
    resolved_prominence_db = validate_peak_prominence_db(prominence_db)

    positive_mask = frequency_hz > 0.0
    if not np.any(positive_mask):
        return []

    frequency_positive = frequency_hz[positive_mask]
    psd_positive = np.maximum(psd_v2_per_hz[positive_mask], np.finfo(float).tiny)
    psd_db = 10.0 * np.log10(psd_positive)

    peak_indices, peak_properties = signal.find_peaks(
        psd_db,
        prominence=resolved_prominence_db,
    )
    if peak_indices.size == 0:
        return []

    prominences = np.asarray(peak_properties["prominences"], dtype=float)
    sort_order = np.argsort(psd_positive[peak_indices])[::-1][:resolved_peak_count]

    peaks: list[PSDPeak] = []
    for order_index in sort_order:
        peak_index = int(peak_indices[order_index])
        peaks.append(
            PSDPeak(
                frequency_hz=float(frequency_positive[peak_index]),
                psd_v2_per_hz=float(psd_positive[peak_index]),
                prominence_db=float(prominences[order_index]),
            )
        )

    return peaks


def convert_single_psd_value_for_display(
    psd_v2_per_hz: float,
    display_unit: str,
    impedance_ohm: float = DEFAULT_IMPEDANCE_OHM,
) -> float:
    """Convert a single PSD value into the selected display unit."""

    values, _ = convert_psd_for_display(
        np.asarray([psd_v2_per_hz], dtype=float),
        display_unit=display_unit,
        impedance_ohm=impedance_ohm,
    )
    return float(values[0])


def format_display_value(
    value: float,
    display_unit: str,
) -> str:
    """Format a display-unit value for human-readable peak summaries."""

    normalized_display_unit = normalize_display_unit(display_unit)
    if normalized_display_unit == DISPLAY_UNIT_V2_PER_HZ:
        return f"{value:.6e}"
    return f"{value:.3f}"


def get_display_unit_label(display_unit: str) -> str:
    """Return the human-readable label for a display unit."""

    normalized = normalize_display_unit(display_unit)
    return DISPLAY_UNIT_LABELS[normalized]


def get_display_formula(display_unit: str, impedance_ohm: float) -> str:
    """Return the conversion formula used for the selected display unit."""

    normalized = normalize_display_unit(display_unit)
    if normalized == DISPLAY_UNIT_V2_PER_HZ:
        return "display = PSD_V2_per_Hz"
    if normalized == DISPLAY_UNIT_DBV_PER_SQRT_HZ:
        return "display = 20*log10(sqrt(PSD_V2_per_Hz) / 1 V/sqrt(Hz))"
    validate_impedance_ohm(impedance_ohm)
    return (
        "display = 10*log10(PSD_V2_per_Hz / "
        f"({impedance_ohm:.10g} Ohm * 1e-3 W))"
    )


def convert_psd_for_display(
    psd_v2_per_hz: np.ndarray,
    display_unit: str,
    impedance_ohm: float = DEFAULT_IMPEDANCE_OHM,
) -> tuple[np.ndarray, str]:
    """
    Convert linear PSD into the requested display quantity.

    Returns:
    1. Converted y values.
    2. Y-axis label.
    """

    normalized = normalize_display_unit(display_unit)
    psd_safe = np.maximum(psd_v2_per_hz, np.finfo(float).tiny)

    if normalized == DISPLAY_UNIT_V2_PER_HZ:
        return psd_safe, "PSD (V$^2$/Hz)"

    if normalized == DISPLAY_UNIT_DBV_PER_SQRT_HZ:
        asd_v_per_sqrt_hz = np.sqrt(psd_safe)
        values = 20.0 * np.log10(asd_v_per_sqrt_hz / 1.0)
        return values, "ASD (dBV/√Hz)"

    resistance = validate_impedance_ohm(impedance_ohm)
    power_psd_w_per_hz = psd_safe / resistance
    values = 10.0 * np.log10(power_psd_w_per_hz / 1e-3)
    return values, "PSD (dBm/Hz)"


def compute_psd(
    data: SignalData,
    nperseg: Optional[int] = None,
    window: str = "hann",
    detrend: DetrendType = "constant",
) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Estimate one-sided PSD using Welch's method."""

    resolved_nperseg = resolve_nperseg(data.voltage.size, nperseg)
    noverlap = resolved_nperseg // 2

    frequency, psd = signal.welch(
        data.voltage,
        fs=data.fs,
        window=window,
        nperseg=resolved_nperseg,
        noverlap=noverlap,
        detrend=detrend,
        scaling="density",
        return_onesided=True,
    )

    return frequency, psd, resolved_nperseg, noverlap


def analyze_csv(
    csv_path: Path,
    nperseg: Optional[int] = None,
    window: str = "hann",
    detrend: DetrendType = "constant",
) -> PSDAnalysisResult:
    """Complete CSV-to-PSD analysis workflow."""

    raw = load_signal_csv(csv_path)
    processed, preprocess_method, preprocess_details = prepare_signal(raw)
    frequency, psd, resolved_nperseg, noverlap = compute_psd(
        processed,
        nperseg=nperseg,
        window=window,
        detrend=detrend,
    )

    return PSDAnalysisResult(
        raw=raw,
        processed=processed,
        frequency=frequency,
        psd=psd,
        nperseg=resolved_nperseg,
        noverlap=noverlap,
        window=window,
        detrend=detrend,
        preprocess_method=preprocess_method,
        preprocess_details=preprocess_details,
    )


def downsample_for_plot(
    time: np.ndarray,
    voltage: np.ndarray,
    max_points: int = MAX_PLOT_POINTS,
) -> tuple[np.ndarray, np.ndarray]:
    """Reduce plotted points for responsive GUI rendering."""

    if time.size <= max_points:
        return time, voltage

    stride = int(np.ceil(time.size / max_points))
    return time[::stride], voltage[::stride]


def populate_figure(
    figure: Figure,
    result: PSDAnalysisResult,
    display_unit: str = DISPLAY_UNIT_V2_PER_HZ,
    impedance_ohm: float = DEFAULT_IMPEDANCE_OHM,
    x_scale: Optional[str] = None,
    y_scale: Optional[str] = None,
    peak_count: int = DEFAULT_PEAK_COUNT,
    peak_prominence_db: float = DEFAULT_PEAK_PROMINENCE_DB,
) -> None:
    """Render time-domain and PSD plots into a matplotlib figure."""

    figure.clear()
    axes = figure.subplots(2, 1, sharex=False)
    ax_signal, ax_psd = axes

    raw_time_plot, raw_voltage_plot = downsample_for_plot(
        result.raw.time,
        result.raw.voltage,
    )
    processed_time_plot, processed_voltage_plot = downsample_for_plot(
        result.processed.time,
        result.processed.voltage,
    )

    ax_signal.plot(
        raw_time_plot,
        raw_voltage_plot,
        color="#b9b9b9",
        linewidth=1.0,
        label="Original signal",
    )
    ax_signal.plot(
        processed_time_plot,
        processed_voltage_plot,
        color="#0b5fa5",
        linewidth=1.2,
        label="Signal used for PSD",
    )
    ax_signal.set_title("Time-Domain Signal")
    ax_signal.set_xlabel("Time (s)")
    ax_signal.set_ylabel("Voltage (V)")
    ax_signal.grid(True, alpha=0.3)
    ax_signal.legend(loc="best")

    resolved_x_scale, resolved_y_scale = resolve_psd_axis_scales(
        display_unit=display_unit,
        x_scale=x_scale,
        y_scale=y_scale,
    )
    y_values, y_label = convert_psd_for_display(
        result.psd,
        display_unit=display_unit,
        impedance_ohm=impedance_ohm,
    )

    frequency_plot = result.frequency
    y_plot = y_values
    mask = np.ones_like(frequency_plot, dtype=bool)
    if resolved_x_scale == AXIS_SCALE_LOG:
        mask &= frequency_plot > 0.0
    if resolved_y_scale == AXIS_SCALE_LOG:
        mask &= y_plot > 0.0

    if not np.any(mask):
        raise ValueError("当前坐标轴比例下没有可绘制的 PSD 数据点。")

    ax_psd.plot(frequency_plot[mask], y_plot[mask], color="#c0392b", linewidth=1.4)
    ax_psd.set_xscale(resolved_x_scale)
    ax_psd.set_yscale(resolved_y_scale)

    peaks = detect_psd_peaks(
        result.frequency,
        result.psd,
        peak_count=peak_count,
        prominence_db=peak_prominence_db,
    )
    if peaks:
        peak_frequency = np.asarray([peak.frequency_hz for peak in peaks], dtype=float)
        peak_display_values = np.asarray(
            [
                convert_single_psd_value_for_display(
                    peak.psd_v2_per_hz,
                    display_unit=display_unit,
                    impedance_ohm=impedance_ohm,
                )
                for peak in peaks
            ],
            dtype=float,
        )
        peak_mask = np.ones_like(peak_frequency, dtype=bool)
        if resolved_x_scale == AXIS_SCALE_LOG:
            peak_mask &= peak_frequency > 0.0
        if resolved_y_scale == AXIS_SCALE_LOG:
            peak_mask &= peak_display_values > 0.0

        ax_psd.scatter(
            peak_frequency[peak_mask],
            peak_display_values[peak_mask],
            color="#1b1b1b",
            s=28,
            zorder=3,
            label="Detected peaks",
        )
        visible_peaks = [peak for peak, keep in zip(peaks, peak_mask) if keep]
        visible_display_values = peak_display_values[peak_mask]
        for rank, (peak, peak_value) in enumerate(
            zip(visible_peaks, visible_display_values),
            start=1,
        ):
            ax_psd.annotate(
                f"P{rank}: {peak.frequency_hz:.6g} Hz",
                xy=(peak.frequency_hz, peak_value),
                xytext=(6, 6),
                textcoords="offset points",
                fontsize=8,
                color="#1b1b1b",
            )

    ax_psd.set_title("Spectral Density via Welch Method")
    ax_psd.set_xlabel("Frequency (Hz)")
    ax_psd.set_ylabel(y_label)
    ax_psd.grid(True, which="both", alpha=0.3)
    if peaks:
        ax_psd.legend(loc="best")

    figure.tight_layout()


def create_figure(
    result: PSDAnalysisResult,
    display_unit: str = DISPLAY_UNIT_V2_PER_HZ,
    impedance_ohm: float = DEFAULT_IMPEDANCE_OHM,
    x_scale: Optional[str] = None,
    y_scale: Optional[str] = None,
    peak_count: int = DEFAULT_PEAK_COUNT,
    peak_prominence_db: float = DEFAULT_PEAK_PROMINENCE_DB,
) -> Figure:
    """Create a new matplotlib figure containing the analysis plots."""

    figure = Figure(figsize=(9.5, 7.2), dpi=100)
    populate_figure(
        figure,
        result,
        display_unit=display_unit,
        impedance_ohm=impedance_ohm,
        x_scale=x_scale,
        y_scale=y_scale,
        peak_count=peak_count,
        peak_prominence_db=peak_prominence_db,
    )
    return figure


def export_psd_csv(
    output_path: Path,
    result: PSDAnalysisResult,
    display_unit: str = DISPLAY_UNIT_V2_PER_HZ,
    impedance_ohm: float = DEFAULT_IMPEDANCE_OHM,
    peak_count: int = DEFAULT_PEAK_COUNT,
    peak_prominence_db: float = DEFAULT_PEAK_PROMINENCE_DB,
) -> None:
    """Export PSD results with method metadata."""

    normalized_display_unit = normalize_display_unit(display_unit)
    validated_impedance = validate_impedance_ohm(impedance_ohm)
    display_values, _ = convert_psd_for_display(
        result.psd,
        display_unit=normalized_display_unit,
        impedance_ohm=validated_impedance,
    )
    display_label = get_display_unit_label(normalized_display_unit)
    display_formula = get_display_formula(
        normalized_display_unit,
        validated_impedance,
    )
    export_display_column = DISPLAY_UNIT_EXPORT_COLUMNS[normalized_display_unit]
    peaks = detect_psd_peaks(
        result.frequency,
        result.psd,
        peak_count=peak_count,
        prominence_db=peak_prominence_db,
    )

    metadata_lines = [
        "# Power Spectral Density estimated with Welch's method",
        f"# Raw CSV rows: {result.raw.voltage.size}",
        f"# Preprocess method: {result.preprocess_method}",
        f"# Preprocess details: {result.preprocess_details}",
        f"# Samples used for PSD: {result.processed.voltage.size}",
        f"# Sampling frequency used for PSD (Hz): {result.processed.fs:.10g}",
        f"# Window: {result.window}",
        f"# nperseg: {result.nperseg}",
        f"# noverlap: {result.noverlap}",
        f"# detrend: {result.detrend}",
        f"# Display unit: {display_label}",
        f"# Display formula: {display_formula}",
        f"# Reference impedance (Ohm): {validated_impedance:.10g}",
        f"# Peak count reported: {validate_peak_count(peak_count)}",
        f"# Minimum peak prominence (dB): {validate_peak_prominence_db(peak_prominence_db):.10g}",
        f"frequency_hz,psd_v2_per_hz,{export_display_column}",
    ]
    for peak_index, peak in enumerate(peaks, start=1):
        peak_display_value = convert_single_psd_value_for_display(
            peak.psd_v2_per_hz,
            display_unit=normalized_display_unit,
            impedance_ohm=validated_impedance,
        )
        metadata_lines.insert(
            -1,
            (
                f"# Peak {peak_index}: f={peak.frequency_hz:.10g} Hz, "
                f"{export_display_column}={peak_display_value:.10g}, "
                f"prominence_db={peak.prominence_db:.10g}"
            ),
        )

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        for line in metadata_lines[:-1]:
            handle.write(f"{line}\n")

        writer = csv.writer(handle)
        writer.writerow(metadata_lines[-1].split(","))
        writer.writerows(
            np.column_stack((result.frequency, result.psd, display_values))
        )


def build_summary(
    result: PSDAnalysisResult,
    source_path: Optional[Path] = None,
    display_unit: str = DISPLAY_UNIT_V2_PER_HZ,
    impedance_ohm: float = DEFAULT_IMPEDANCE_OHM,
    x_scale: Optional[str] = None,
    y_scale: Optional[str] = None,
    peak_count: int = DEFAULT_PEAK_COUNT,
    peak_prominence_db: float = DEFAULT_PEAK_PROMINENCE_DB,
) -> str:
    """Build a concise analysis summary for GUI or CLI output."""

    duration = float(result.processed.time[-1] - result.processed.time[0])
    source = source_path.name if source_path is not None else "未指定"
    normalized_display_unit = normalize_display_unit(display_unit)
    display_label = get_display_unit_label(normalized_display_unit)
    validated_peak_count = validate_peak_count(peak_count)
    validated_peak_prominence_db = validate_peak_prominence_db(peak_prominence_db)
    resolved_x_scale, resolved_y_scale = resolve_psd_axis_scales(
        display_unit=normalized_display_unit,
        x_scale=x_scale,
        y_scale=y_scale,
    )
    peaks = detect_psd_peaks(
        result.frequency,
        result.psd,
        peak_count=validated_peak_count,
        prominence_db=validated_peak_prominence_db,
    )

    lines = [
        f"文件: {source}",
        f"原始 CSV 行数: {result.raw.voltage.size}",
        f"预处理方法: {result.preprocess_method}",
        f"用于 PSD 的样本数: {result.processed.voltage.size}",
        f"用于 PSD 的采样频率: {result.processed.fs:.6g} Hz",
        f"记录时长: {duration:.6g} s",
        f"Welch 窗函数: {result.window}",
        f"Welch nperseg: {result.nperseg}",
        f"Welch noverlap: {result.noverlap}",
        f"Detrend: {result.detrend}",
        f"图中纵坐标单位: {display_label}",
        f"PSD 横轴比例: {resolved_x_scale}",
        f"PSD 纵轴比例: {resolved_y_scale}",
        f"自动寻峰数量: {validated_peak_count}",
        f"最小峰值 prominence: {validated_peak_prominence_db:.6g} dB",
        f"说明: {result.preprocess_details}",
    ]
    if normalized_display_unit == DISPLAY_UNIT_DBM_PER_HZ:
        validated_impedance = validate_impedance_ohm(impedance_ohm)
        lines.append(f"dBm 参考阻抗: {validated_impedance:.6g} Ohm")
    if peaks:
        lines.append("自动寻峰结果:")
        for peak_index, peak in enumerate(peaks, start=1):
            peak_display_value = convert_single_psd_value_for_display(
                peak.psd_v2_per_hz,
                display_unit=normalized_display_unit,
                impedance_ohm=impedance_ohm,
            )
            lines.append(
                (
                    f"  P{peak_index}: {peak.frequency_hz:.6g} Hz, "
                    f"{display_label}={format_display_value(peak_display_value, normalized_display_unit)}, "
                    f"prominence={peak.prominence_db:.3f} dB"
                )
            )
    else:
        lines.append("自动寻峰结果: 未检测到满足 prominence 阈值的峰。")
    return "\n".join(lines)


def run_cli(args: argparse.Namespace) -> None:
    """Run the reproducible command-line workflow."""

    detrend = normalize_detrend(args.detrend)
    display_unit = normalize_display_unit(args.y_unit)
    impedance_ohm = validate_impedance_ohm(args.impedance_ohm)
    peak_count = validate_peak_count(args.peak_count)
    peak_prominence_db = validate_peak_prominence_db(args.peak_prominence_db)
    x_scale = None if args.x_scale is None else normalize_axis_scale(args.x_scale)
    y_scale = None if args.y_scale is None else normalize_axis_scale(args.y_scale)
    resolve_psd_axis_scales(
        display_unit=display_unit,
        x_scale=x_scale,
        y_scale=y_scale,
    )
    result = analyze_csv(
        csv_path=args.input,
        nperseg=args.nperseg,
        window=args.window,
        detrend=detrend,
    )

    if args.output is not None:
        export_psd_csv(
            args.output,
            result,
            display_unit=display_unit,
            impedance_ohm=impedance_ohm,
            peak_count=peak_count,
            peak_prominence_db=peak_prominence_db,
        )

    if args.plot is not None:
        figure = create_figure(
            result,
            display_unit=display_unit,
            impedance_ohm=impedance_ohm,
            x_scale=x_scale,
            y_scale=y_scale,
            peak_count=peak_count,
            peak_prominence_db=peak_prominence_db,
        )
        figure.savefig(args.plot, dpi=300)

    print(
        build_summary(
            result,
            source_path=args.input,
            display_unit=display_unit,
            impedance_ohm=impedance_ohm,
            x_scale=x_scale,
            y_scale=y_scale,
            peak_count=peak_count,
            peak_prominence_db=peak_prominence_db,
        )
    )


def launch_gui() -> None:
    """Launch the Tkinter front-end."""

    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

    class PSDGuiApp(ttk.Frame):
        def __init__(self, master: tk.Tk) -> None:
            super().__init__(master, padding=12)
            self.master = master
            self.csv_path: Optional[Path] = None
            self.result: Optional[PSDAnalysisResult] = None

            self.file_var = tk.StringVar()
            self.nperseg_var = tk.StringVar(value="auto")
            self.window_var = tk.StringVar(value="hann")
            self.detrend_var = tk.StringVar(value="constant")
            self.y_unit_var = tk.StringVar(
                value=DISPLAY_UNIT_LABELS[DISPLAY_UNIT_V2_PER_HZ]
            )
            self.impedance_var = tk.StringVar(value=f"{DEFAULT_IMPEDANCE_OHM:.10g}")
            self.x_scale_var = tk.StringVar(value=AXIS_SCALE_LABELS[AXIS_SCALE_LINEAR])
            self.y_scale_var = tk.StringVar(value=AXIS_SCALE_LABELS[AXIS_SCALE_LOG])
            self.peak_count_var = tk.StringVar(value=str(DEFAULT_PEAK_COUNT))
            self.peak_prominence_var = tk.StringVar(
                value=f"{DEFAULT_PEAK_PROMINENCE_DB:.10g}"
            )
            self.status_var = tk.StringVar(value="请选择 CSV 文件。")

            self.figure = Figure(figsize=(9.5, 7.2), dpi=100)

            self._configure_root()
            self._build_layout()
            self._draw_placeholder()

        def _configure_root(self) -> None:
            self.master.title("PSD Power Spectral Density Analyzer")
            self.master.geometry("1280x800")
            self.master.minsize(1080, 720)
            self.master.rowconfigure(0, weight=1)
            self.master.columnconfigure(0, weight=1)
            self.grid(row=0, column=0, sticky="nsew")
            self.rowconfigure(0, weight=1)
            self.columnconfigure(1, weight=1)

        def _build_layout(self) -> None:
            control_panel = ttk.Frame(self)
            control_panel.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
            plot_panel = ttk.Frame(self)
            plot_panel.grid(row=0, column=1, sticky="nsew")
            plot_panel.rowconfigure(0, weight=1)
            plot_panel.rowconfigure(1, weight=0)
            plot_panel.columnconfigure(0, weight=1)

            self._build_file_section(control_panel)
            self._build_parameter_section(control_panel)
            self._build_action_section(control_panel)
            self._build_summary_section(control_panel)
            self._build_note_section(control_panel)
            self._build_status_bar(control_panel)

            self.canvas = FigureCanvasTkAgg(self.figure, master=plot_panel)
            self.canvas_widget = self.canvas.get_tk_widget()
            self.canvas_widget.grid(row=0, column=0, sticky="nsew")
            toolbar_frame = ttk.Frame(plot_panel)
            toolbar_frame.grid(row=1, column=0, sticky="ew")
            self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
            self.toolbar.update()

        def _build_file_section(self, parent: ttk.Frame) -> None:
            frame = ttk.LabelFrame(parent, text="CSV 输入", padding=10)
            frame.grid(row=0, column=0, sticky="ew")
            frame.columnconfigure(0, weight=1)

            entry = ttk.Entry(frame, textvariable=self.file_var, width=48)
            entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
            browse_button = ttk.Button(frame, text="浏览...", command=self.select_file)
            browse_button.grid(row=0, column=1, sticky="e")

        def _build_parameter_section(self, parent: ttk.Frame) -> None:
            frame = ttk.LabelFrame(parent, text="分析参数", padding=10)
            frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))

            ttk.Label(frame, text="时间预处理: 自动").grid(
                row=0, column=0, sticky="w"
            )
            ttk.Label(frame, text="nperseg:").grid(row=1, column=0, sticky="w", pady=(8, 0))
            ttk.Entry(frame, textvariable=self.nperseg_var, width=18).grid(
                row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0)
            )

            ttk.Label(frame, text="Window:").grid(row=2, column=0, sticky="w", pady=(8, 0))
            ttk.Combobox(
                frame,
                textvariable=self.window_var,
                values=("hann", "hamming", "blackman", "boxcar"),
                width=16,
                state="readonly",
            ).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

            ttk.Label(frame, text="Detrend:").grid(row=3, column=0, sticky="w", pady=(8, 0))
            ttk.Combobox(
                frame,
                textvariable=self.detrend_var,
                values=("constant", "linear", "none"),
                width=16,
                state="readonly",
            ).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(8, 0))

            ttk.Label(frame, text="Y-axis unit:").grid(row=4, column=0, sticky="w", pady=(8, 0))
            self.y_unit_combo = ttk.Combobox(
                frame,
                textvariable=self.y_unit_var,
                values=tuple(DISPLAY_UNIT_LABELS[unit] for unit in DISPLAY_UNIT_CHOICES),
                width=16,
                state="readonly",
            )
            self.y_unit_combo.grid(row=4, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
            self.y_unit_combo.bind("<<ComboboxSelected>>", self.on_display_option_changed)

            ttk.Label(frame, text="Impedance (Ohm):").grid(
                row=5, column=0, sticky="w", pady=(8, 0)
            )
            self.impedance_entry = ttk.Entry(
                frame,
                textvariable=self.impedance_var,
                width=18,
            )
            self.impedance_entry.grid(row=5, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
            self.impedance_entry.bind("<Return>", self.on_display_option_changed)
            self.impedance_entry.bind("<FocusOut>", self.on_display_option_changed)
            ttk.Label(frame, text="PSD X scale:").grid(row=6, column=0, sticky="w", pady=(8, 0))
            self.x_scale_combo = ttk.Combobox(
                frame,
                textvariable=self.x_scale_var,
                values=tuple(AXIS_SCALE_LABELS[scale] for scale in AXIS_SCALE_CHOICES),
                width=16,
                state="readonly",
            )
            self.x_scale_combo.grid(row=6, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
            self.x_scale_combo.bind("<<ComboboxSelected>>", self.on_display_option_changed)

            ttk.Label(frame, text="PSD Y scale:").grid(row=7, column=0, sticky="w", pady=(8, 0))
            self.y_scale_combo = ttk.Combobox(
                frame,
                textvariable=self.y_scale_var,
                values=tuple(AXIS_SCALE_LABELS[scale] for scale in AXIS_SCALE_CHOICES),
                width=16,
                state="readonly",
            )
            self.y_scale_combo.grid(row=7, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
            self.y_scale_combo.bind("<<ComboboxSelected>>", self.on_display_option_changed)

            ttk.Label(frame, text="Peak count:").grid(row=8, column=0, sticky="w", pady=(8, 0))
            self.peak_count_entry = ttk.Entry(
                frame,
                textvariable=self.peak_count_var,
                width=18,
            )
            self.peak_count_entry.grid(row=8, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
            self.peak_count_entry.bind("<Return>", self.on_display_option_changed)
            self.peak_count_entry.bind("<FocusOut>", self.on_display_option_changed)

            ttk.Label(frame, text="Prominence (dB):").grid(
                row=9, column=0, sticky="w", pady=(8, 0)
            )
            self.peak_prominence_entry = ttk.Entry(
                frame,
                textvariable=self.peak_prominence_var,
                width=18,
            )
            self.peak_prominence_entry.grid(
                row=9, column=1, sticky="w", padx=(8, 0), pady=(8, 0)
            )
            self.peak_prominence_entry.bind("<Return>", self.on_display_option_changed)
            self.peak_prominence_entry.bind("<FocusOut>", self.on_display_option_changed)
            self._update_scale_control_states()

        def _build_action_section(self, parent: ttk.Frame) -> None:
            frame = ttk.LabelFrame(parent, text="操作", padding=10)
            frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))

            ttk.Button(frame, text="计算 PSD", command=self.run_analysis).grid(
                row=0, column=0, sticky="ew"
            )
            self.export_button = ttk.Button(
                frame,
                text="导出 PSD CSV",
                command=self.export_results,
                state="disabled",
            )
            self.export_button.grid(row=1, column=0, sticky="ew", pady=(8, 0))

            self.save_plot_button = ttk.Button(
                frame,
                text="保存图像 PNG",
                command=self.save_figure,
                state="disabled",
            )
            self.save_plot_button.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        def _build_summary_section(self, parent: ttk.Frame) -> None:
            frame = ttk.LabelFrame(parent, text="分析摘要", padding=10)
            frame.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
            parent.rowconfigure(3, weight=1)

            self.summary_text = scrolledtext.ScrolledText(
                frame,
                width=42,
                height=18,
                wrap=tk.WORD,
                font=("TkDefaultFont", 10),
            )
            self.summary_text.grid(row=0, column=0, sticky="nsew")
            self.summary_text.configure(state="disabled")

        def _build_note_section(self, parent: ttk.Frame) -> None:
            frame = ttk.LabelFrame(parent, text="方法说明", padding=10)
            frame.grid(row=4, column=0, sticky="ew", pady=(12, 0))

            note = (
                "1. 输入格式为两列 CSV：时间(s)、电压(V)，首行为表头。\n"
                "2. 若时间列存在重复或非均匀步长，本程序会自动重建均匀时间轴。\n"
                "3. PSD 使用 Welch 方法估计，默认 50% 重叠。\n"
                "4. 纵坐标支持 V^2/Hz、dBV/√Hz、dBm/Hz；其中 dBm/Hz 依赖参考阻抗。\n"
                "5. 右侧图支持 Matplotlib 交互：缩放、平移、框选、保存。\n"
                "6. PSD 横轴支持 linear/log；纵轴对 V^2/Hz 支持 linear/log。\n"
                "7. 自动寻峰默认报告前 5 个满足 prominence 条件的谱峰。\n"
                "8. Rigol 这类导出文件通常是时间显示精度不足，而非真实重复采样。"
            )
            ttk.Label(frame, text=note, justify="left", wraplength=340).grid(
                row=0, column=0, sticky="w"
            )

        def _build_status_bar(self, parent: ttk.Frame) -> None:
            label = ttk.Label(parent, textvariable=self.status_var, foreground="#444444")
            label.grid(row=5, column=0, sticky="ew", pady=(12, 0))

        def _draw_placeholder(self) -> None:
            self.figure.clear()
            axis = self.figure.add_subplot(111)
            axis.text(
                0.5,
                0.5,
                "导入 CSV 文件后点击“计算 PSD”",
                ha="center",
                va="center",
                fontsize=14,
            )
            axis.set_axis_off()
            self.canvas.draw_idle() if hasattr(self, "canvas") else None

        def _parse_nperseg(self) -> Optional[int]:
            raw_value = self.nperseg_var.get().strip().lower()
            if raw_value in {"", "auto"}:
                return None
            return int(raw_value)

        def _parse_display_settings(self) -> tuple[str, float, str, str, int, float]:
            display_unit = normalize_display_unit(self.y_unit_var.get())
            impedance_ohm = validate_impedance_ohm(float(self.impedance_var.get().strip()))
            x_scale = normalize_axis_scale(self.x_scale_var.get())
            y_scale = normalize_axis_scale(self.y_scale_var.get())
            peak_count = validate_peak_count(int(self.peak_count_var.get().strip()))
            peak_prominence_db = validate_peak_prominence_db(
                float(self.peak_prominence_var.get().strip())
            )
            resolve_psd_axis_scales(
                display_unit=display_unit,
                x_scale=x_scale,
                y_scale=y_scale,
            )
            return (
                display_unit,
                impedance_ohm,
                x_scale,
                y_scale,
                peak_count,
                peak_prominence_db,
            )

        def _update_scale_control_states(self) -> None:
            display_unit = normalize_display_unit(self.y_unit_var.get())
            if display_unit == DISPLAY_UNIT_DBM_PER_HZ:
                self.impedance_entry.configure(state="normal")
            else:
                self.impedance_entry.configure(state="disabled")

            if display_unit == DISPLAY_UNIT_V2_PER_HZ:
                self.y_scale_combo.configure(state="readonly")
            else:
                self.y_scale_var.set(AXIS_SCALE_LABELS[AXIS_SCALE_LINEAR])
                self.y_scale_combo.configure(state="disabled")

        def _refresh_visualization(self) -> None:
            if self.result is None:
                return

            (
                display_unit,
                impedance_ohm,
                x_scale,
                y_scale,
                peak_count,
                peak_prominence_db,
            ) = self._parse_display_settings()
            populate_figure(
                self.figure,
                self.result,
                display_unit=display_unit,
                impedance_ohm=impedance_ohm,
                x_scale=x_scale,
                y_scale=y_scale,
                peak_count=peak_count,
                peak_prominence_db=peak_prominence_db,
            )
            self.canvas.draw_idle()
            self._update_summary(
                build_summary(
                    self.result,
                    source_path=self.csv_path,
                    display_unit=display_unit,
                    impedance_ohm=impedance_ohm,
                    x_scale=x_scale,
                    y_scale=y_scale,
                    peak_count=peak_count,
                    peak_prominence_db=peak_prominence_db,
                )
            )

        def on_display_option_changed(self, _event: object | None = None) -> None:
            self._update_scale_control_states()
            if self.result is None:
                return

            try:
                self._refresh_visualization()
            except Exception as exc:
                self.status_var.set("绘图显示参数无效。")
                messagebox.showerror("显示设置错误", str(exc))

        def _update_summary(self, text: str) -> None:
            self.summary_text.configure(state="normal")
            self.summary_text.delete("1.0", tk.END)
            self.summary_text.insert(tk.END, text)
            self.summary_text.configure(state="disabled")

        def select_file(self) -> None:
            file_path = filedialog.askopenfilename(
                title="选择 CSV 文件",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not file_path:
                return

            self.csv_path = Path(file_path)
            self.file_var.set(str(self.csv_path))
            self.status_var.set("文件已选择，可以开始计算。")

        def run_analysis(self) -> None:
            if self.csv_path is None:
                messagebox.showwarning("缺少输入", "请先选择一个 CSV 文件。")
                return

            try:
                nperseg = self._parse_nperseg()
                detrend = normalize_detrend(self.detrend_var.get())
                (
                    display_unit,
                    impedance_ohm,
                    x_scale,
                    y_scale,
                    peak_count,
                    peak_prominence_db,
                ) = self._parse_display_settings()
                self.result = analyze_csv(
                    csv_path=self.csv_path,
                    nperseg=nperseg,
                    window=self.window_var.get(),
                    detrend=detrend,
                )
            except Exception as exc:
                self.result = None
                self.export_button.configure(state="disabled")
                self.save_plot_button.configure(state="disabled")
                self.status_var.set("计算失败。")
                messagebox.showerror("计算失败", str(exc))
                return

            populate_figure(
                self.figure,
                self.result,
                display_unit=display_unit,
                impedance_ohm=impedance_ohm,
                x_scale=x_scale,
                y_scale=y_scale,
                peak_count=peak_count,
                peak_prominence_db=peak_prominence_db,
            )
            self.canvas.draw_idle()
            self._update_summary(
                build_summary(
                    self.result,
                    source_path=self.csv_path,
                    display_unit=display_unit,
                    impedance_ohm=impedance_ohm,
                    x_scale=x_scale,
                    y_scale=y_scale,
                    peak_count=peak_count,
                    peak_prominence_db=peak_prominence_db,
                )
            )
            self.export_button.configure(state="normal")
            self.save_plot_button.configure(state="normal")
            self.status_var.set("PSD 计算完成。")

        def export_results(self) -> None:
            if self.result is None or self.csv_path is None:
                return

            default_name = self.csv_path.with_name(f"{self.csv_path.stem}_psd.csv")
            output_path = filedialog.asksaveasfilename(
                title="保存 PSD 结果",
                initialfile=default_name.name,
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
            )
            if not output_path:
                return

            try:
                (
                    display_unit,
                    impedance_ohm,
                    _x_scale,
                    _y_scale,
                    peak_count,
                    peak_prominence_db,
                ) = self._parse_display_settings()
                export_psd_csv(
                    Path(output_path),
                    self.result,
                    display_unit=display_unit,
                    impedance_ohm=impedance_ohm,
                    peak_count=peak_count,
                    peak_prominence_db=peak_prominence_db,
                )
            except Exception as exc:
                messagebox.showerror("导出失败", str(exc))
                return

            self.status_var.set(f"PSD 结果已保存到: {output_path}")

        def save_figure(self) -> None:
            if self.result is None or self.csv_path is None:
                return

            default_name = self.csv_path.with_name(f"{self.csv_path.stem}_psd.png")
            output_path = filedialog.asksaveasfilename(
                title="保存 PSD 图像",
                initialfile=default_name.name,
                defaultextension=".png",
                filetypes=[("PNG files", "*.png")],
            )
            if not output_path:
                return

            try:
                self.figure.savefig(output_path, dpi=300)
            except Exception as exc:
                messagebox.showerror("保存失败", str(exc))
                return

            self.status_var.set(f"图像已保存到: {output_path}")

    root = tk.Tk()
    PSDGuiApp(root)
    root.mainloop()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Compute power spectral density from a two-column CSV file. "
            "If no input file is given, the GUI is launched."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to the CSV input file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for exported PSD CSV.",
    )
    parser.add_argument(
        "--plot",
        type=Path,
        help="Optional path for exported PSD PNG.",
    )
    parser.add_argument(
        "--nperseg",
        type=int,
        default=None,
        help="Welch segment length. If omitted, a reasonable value is chosen automatically.",
    )
    parser.add_argument(
        "--window",
        choices=("hann", "hamming", "blackman", "boxcar"),
        default="hann",
        help="Welch window function.",
    )
    parser.add_argument(
        "--detrend",
        choices=("constant", "linear", "none"),
        default="constant",
        help="Detrend mode before PSD estimation.",
    )
    parser.add_argument(
        "--y-unit",
        choices=DISPLAY_UNIT_CHOICES,
        default=DISPLAY_UNIT_V2_PER_HZ,
        help=(
            "Displayed y-axis unit: "
            "v2_per_hz, dbv_per_sqrt_hz, or dbm_per_hz."
        ),
    )
    parser.add_argument(
        "--impedance-ohm",
        type=float,
        default=DEFAULT_IMPEDANCE_OHM,
        help="Reference impedance in ohms for dBm/Hz conversion.",
    )
    parser.add_argument(
        "--x-scale",
        choices=AXIS_SCALE_CHOICES,
        default=None,
        help="PSD x-axis scale for exported plots: linear or log.",
    )
    parser.add_argument(
        "--y-scale",
        choices=AXIS_SCALE_CHOICES,
        default=None,
        help=(
            "PSD y-axis scale for exported plots: linear or log. "
            "For dBV/√Hz and dBm/Hz, linear is required."
        ),
    )
    parser.add_argument(
        "--peak-count",
        type=int,
        default=DEFAULT_PEAK_COUNT,
        help="Maximum number of automatically reported PSD peaks.",
    )
    parser.add_argument(
        "--peak-prominence-db",
        type=float,
        default=DEFAULT_PEAK_PROMINENCE_DB,
        help="Minimum peak prominence in dB for automatic peak finding.",
    )
    return parser.parse_args()


def main() -> None:
    """Application entry point."""

    args = parse_args()
    if args.input is None:
        launch_gui()
        return

    run_cli(args)


if __name__ == "__main__":
    main()
