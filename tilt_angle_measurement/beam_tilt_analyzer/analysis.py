"""Numerical routines for Gaussian beam tracking and tilt-noise analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import linregress


FWHM_PER_SIGMA = 2.0 * math.sqrt(2.0 * math.log(2.0))


@dataclass
class GeometrySettings:
    optical_path_m: float = 10.0
    camera_to_screen_m: float = 0.25
    lens_focal_length_mm: float = 25.0
    pixel_size_um: float = 3.45
    static_tilt_mrad: float = 1.28
    analysis_axis: str = "Y"
    use_manual_scale: bool = False
    manual_scale_mm_per_px: float = 0.031


@dataclass
class AnalysisSettings:
    roi_x: int = 0
    roi_y: int = 0
    roi_width: int = 1440
    roi_height: int = 1080
    threshold_fraction: float = 0.10
    subtract_background: bool = False
    gaussian_refinement: bool = True
    analysis_stride: int = 1
    display_fps: float = 10.0
    background_average_count: int = 16


@dataclass
class GaussianEstimate:
    amplitude: float
    x0_px: float
    y0_px: float
    sigma_x_px: float
    sigma_y_px: float
    sigma_major_px: float
    sigma_minor_px: float
    theta_deg: float
    background_level: float
    total_intensity: float
    peak_intensity: float


@dataclass
class FitDiagnostics:
    success: bool
    rmse: float
    r_squared: float


@dataclass
class FrameAnalysisResult:
    timestamp_s: float
    frame_index: int
    roi_x: int
    roi_y: int
    roi_width: int
    roi_height: int
    center_x_px: float
    center_y_px: float
    center_x_roi_px: float
    center_y_roi_px: float
    sigma_x_px: float
    sigma_y_px: float
    sigma_major_px: float
    sigma_minor_px: float
    fwhm_x_px: float
    fwhm_y_px: float
    fwhm_major_px: float
    fwhm_minor_px: float
    theta_deg: float
    amplitude: float
    background_level: float
    total_intensity: float
    peak_intensity: float
    fit_success: bool
    fit_rmse: float
    fit_r_squared: float
    scale_mm_per_px: float
    dx_mm: float
    dy_mm: float
    tilt_x_urad: float
    tilt_y_urad: float
    radial_tilt_urad: float
    selected_tilt_urad: float
    absolute_tilt_mrad: float
    acquisition_fps: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clipped_roi(
    image_shape: tuple[int, int],
    roi_x: int,
    roi_y: int,
    roi_width: int,
    roi_height: int,
) -> tuple[slice, slice, tuple[int, int, int, int]]:
    """Return clipped ROI slices and the effective ROI tuple."""
    height, width = image_shape
    x0 = max(0, min(width - 1, int(roi_x)))
    y0 = max(0, min(height - 1, int(roi_y)))
    roi_w = max(1, int(roi_width))
    roi_h = max(1, int(roi_height))
    x1 = min(width, x0 + roi_w)
    y1 = min(height, y0 + roi_h)
    return slice(y0, y1), slice(x0, x1), (x0, y0, x1 - x0, y1 - y0)


def scale_mm_per_px(geometry: GeometrySettings) -> float:
    """Estimate the object-plane scale from thin-lens imaging."""
    if geometry.use_manual_scale:
        return max(1.0e-9, float(geometry.manual_scale_mm_per_px))
    object_distance_mm = geometry.camera_to_screen_m * 1000.0
    focal_length_mm = geometry.lens_focal_length_mm
    pixel_size_mm = geometry.pixel_size_um * 1.0e-3
    if focal_length_mm <= 0.0:
        raise ValueError("Lens focal length must be positive.")
    if object_distance_mm <= focal_length_mm:
        raise ValueError(
            "Camera-to-screen distance must be larger than the lens focal length."
        )
    magnification = focal_length_mm / (object_distance_mm - focal_length_mm)
    return pixel_size_mm / magnification


def displacement_to_tilt_urad(displacement_mm: float, optical_path_m: float) -> float:
    """Convert screen displacement to angular jitter using the small-angle approximation."""
    optical_path_mm = optical_path_m * 1000.0
    if optical_path_mm <= 0.0:
        raise ValueError("Optical path length must be positive.")
    return displacement_mm / optical_path_mm * 1.0e6


def _rotated_gaussian(
    coords: tuple[np.ndarray, np.ndarray],
    amplitude: float,
    x0_px: float,
    y0_px: float,
    sigma_x_px: float,
    sigma_y_px: float,
    theta_rad: float,
    offset: float,
) -> np.ndarray:
    x_grid, y_grid = coords
    cos_t = math.cos(theta_rad)
    sin_t = math.sin(theta_rad)
    x_shift = x_grid - x0_px
    y_shift = y_grid - y0_px
    x_rot = cos_t * x_shift + sin_t * y_shift
    y_rot = -sin_t * x_shift + cos_t * y_shift
    exponent = -0.5 * (
        np.square(x_rot / sigma_x_px) + np.square(y_rot / sigma_y_px)
    )
    return offset + amplitude * np.exp(exponent)


def preprocess_roi(
    roi_image: np.ndarray,
    roi_background: np.ndarray | None,
    subtract_background: bool,
) -> tuple[np.ndarray, float]:
    """Convert the ROI to float, subtract the dark frame, and clip negatives."""
    roi_float = roi_image.astype(np.float64, copy=False)
    background_level = float(np.median(roi_float))
    if subtract_background and roi_background is not None:
        roi_float = roi_float - roi_background.astype(np.float64, copy=False)
        background_level = float(np.median(roi_float))
    roi_float = np.clip(roi_float, 0.0, None)
    return roi_float, background_level


def estimate_gaussian_moments(
    roi_image: np.ndarray,
    threshold_fraction: float,
    background_level: float,
) -> GaussianEstimate | None:
    """Estimate Gaussian beam parameters from intensity moments."""
    peak_intensity = float(np.max(roi_image))
    if not np.isfinite(peak_intensity) or peak_intensity <= 0.0:
        return None

    threshold_fraction = max(0.0, min(0.95, threshold_fraction))
    threshold = peak_intensity * threshold_fraction
    weights = np.where(roi_image >= threshold, roi_image, 0.0)
    if float(np.sum(weights)) <= 0.0:
        weights = roi_image

    total_intensity = float(np.sum(weights))
    if total_intensity <= 0.0:
        return None

    y_idx, x_idx = np.indices(roi_image.shape, dtype=np.float64)
    x0_px = float(np.sum(weights * x_idx) / total_intensity)
    y0_px = float(np.sum(weights * y_idx) / total_intensity)

    dx = x_idx - x0_px
    dy = y_idx - y0_px
    cov_xx = float(np.sum(weights * dx * dx) / total_intensity)
    cov_yy = float(np.sum(weights * dy * dy) / total_intensity)
    cov_xy = float(np.sum(weights * dx * dy) / total_intensity)
    covariance = np.array([[cov_xx, cov_xy], [cov_xy, cov_yy]], dtype=np.float64)
    evals, evecs = np.linalg.eigh(covariance)
    evals = np.maximum(evals, 1.0e-9)
    order = np.argsort(evals)[::-1]
    evals = evals[order]
    evecs = evecs[:, order]

    sigma_major_px = float(np.sqrt(evals[0]))
    sigma_minor_px = float(np.sqrt(evals[1]))
    theta_deg = float(np.degrees(np.arctan2(evecs[1, 0], evecs[0, 0])))

    sigma_x_px = max(math.sqrt(max(cov_xx, 1.0e-9)), 1.0e-3)
    sigma_y_px = max(math.sqrt(max(cov_yy, 1.0e-9)), 1.0e-3)
    amplitude = peak_intensity - max(background_level, 0.0)

    return GaussianEstimate(
        amplitude=float(max(amplitude, 1.0e-6)),
        x0_px=x0_px,
        y0_px=y0_px,
        sigma_x_px=sigma_x_px,
        sigma_y_px=sigma_y_px,
        sigma_major_px=sigma_major_px,
        sigma_minor_px=sigma_minor_px,
        theta_deg=theta_deg,
        background_level=float(max(background_level, 0.0)),
        total_intensity=float(np.sum(roi_image)),
        peak_intensity=peak_intensity,
    )


def refine_gaussian_fit(
    roi_image: np.ndarray,
    initial: GaussianEstimate,
) -> tuple[GaussianEstimate, FitDiagnostics]:
    """Refine the Gaussian estimate with a rotated 2D least-squares fit."""
    y_idx, x_idx = np.indices(roi_image.shape, dtype=np.float64)
    sigma_x_init = max(initial.sigma_x_px, 0.8)
    sigma_y_init = max(initial.sigma_y_px, 0.8)
    initial_vector = (
        initial.amplitude,
        initial.x0_px,
        initial.y0_px,
        sigma_x_init,
        sigma_y_init,
        math.radians(initial.theta_deg),
        initial.background_level,
    )

    lower_bounds = (
        0.0,
        0.0,
        0.0,
        0.25,
        0.25,
        -math.pi / 2.0,
        0.0,
    )
    upper_bounds = (
        float(np.max(roi_image) * 2.0 + 1.0),
        float(roi_image.shape[1] - 1),
        float(roi_image.shape[0] - 1),
        float(max(roi_image.shape[1], 2)),
        float(max(roi_image.shape[0], 2)),
        math.pi / 2.0,
        float(np.max(roi_image)),
    )

    try:
        popt, _ = curve_fit(
            _rotated_gaussian,
            (x_idx.ravel(), y_idx.ravel()),
            roi_image.ravel(),
            p0=initial_vector,
            bounds=(lower_bounds, upper_bounds),
            maxfev=6000,
        )
        fitted = _rotated_gaussian((x_idx, y_idx), *popt).reshape(roi_image.shape)
        residual = roi_image - fitted
        rmse = float(np.sqrt(np.mean(np.square(residual))))
        variance = float(np.var(roi_image))
        r_squared = 1.0 - float(np.var(residual)) / variance if variance > 0.0 else 1.0

        amplitude, x0_px, y0_px, sigma_x_px, sigma_y_px, theta_rad, offset = popt
        sigma_major_px = float(max(sigma_x_px, sigma_y_px))
        sigma_minor_px = float(min(sigma_x_px, sigma_y_px))
        theta_deg = float(np.degrees(theta_rad))
        if sigma_y_px > sigma_x_px:
            theta_deg += 90.0
        estimate = GaussianEstimate(
            amplitude=float(amplitude),
            x0_px=float(x0_px),
            y0_px=float(y0_px),
            sigma_x_px=float(sigma_x_px),
            sigma_y_px=float(sigma_y_px),
            sigma_major_px=sigma_major_px,
            sigma_minor_px=sigma_minor_px,
            theta_deg=theta_deg,
            background_level=float(offset),
            total_intensity=float(np.sum(np.clip(fitted - offset, 0.0, None))),
            peak_intensity=float(np.max(fitted)),
        )
        diagnostics = FitDiagnostics(success=True, rmse=rmse, r_squared=r_squared)
        return estimate, diagnostics
    except Exception:
        return initial, FitDiagnostics(success=False, rmse=float("nan"), r_squared=float("nan"))


def analyze_frame(
    frame: np.ndarray,
    timestamp_s: float,
    frame_index: int,
    geometry: GeometrySettings,
    analysis: AnalysisSettings,
    background_frame: np.ndarray | None,
    reference_center_px: tuple[float, float] | None,
    acquisition_fps: float,
) -> tuple[FrameAnalysisResult | None, np.ndarray]:
    """Analyze one frame and return the fitted beam parameters and the raw ROI."""
    if frame.ndim != 2:
        raise ValueError("Only monochrome 2D images are supported.")

    roi_slice_y, roi_slice_x, roi_tuple = clipped_roi(
        frame.shape,
        analysis.roi_x,
        analysis.roi_y,
        analysis.roi_width,
        analysis.roi_height,
    )
    roi_image = frame[roi_slice_y, roi_slice_x]
    roi_background = None if background_frame is None else background_frame[roi_slice_y, roi_slice_x]
    processed_roi, background_level = preprocess_roi(
        roi_image,
        roi_background,
        analysis.subtract_background,
    )

    estimate = estimate_gaussian_moments(
        processed_roi,
        threshold_fraction=analysis.threshold_fraction,
        background_level=background_level,
    )
    if estimate is None:
        return None, roi_image

    if analysis.gaussian_refinement:
        estimate, diagnostics = refine_gaussian_fit(processed_roi, estimate)
    else:
        diagnostics = FitDiagnostics(success=False, rmse=float("nan"), r_squared=float("nan"))

    scale = scale_mm_per_px(geometry)
    center_x_px = roi_tuple[0] + estimate.x0_px
    center_y_px = roi_tuple[1] + estimate.y0_px

    if reference_center_px is None:
        dx_px = 0.0
        dy_px = 0.0
    else:
        dx_px = center_x_px - reference_center_px[0]
        dy_px = center_y_px - reference_center_px[1]

    dx_mm = dx_px * scale
    dy_mm = dy_px * scale
    tilt_x_urad = displacement_to_tilt_urad(dx_mm, geometry.optical_path_m)
    tilt_y_urad = displacement_to_tilt_urad(dy_mm, geometry.optical_path_m)
    radial_tilt_urad = float(math.hypot(tilt_x_urad, tilt_y_urad))

    axis_map = {
        "X": tilt_x_urad,
        "Y": tilt_y_urad,
        "Radial": radial_tilt_urad,
    }
    selected_tilt_urad = axis_map.get(geometry.analysis_axis, tilt_y_urad)
    absolute_tilt_mrad = geometry.static_tilt_mrad + selected_tilt_urad / 1000.0

    result = FrameAnalysisResult(
        timestamp_s=timestamp_s,
        frame_index=frame_index,
        roi_x=roi_tuple[0],
        roi_y=roi_tuple[1],
        roi_width=roi_tuple[2],
        roi_height=roi_tuple[3],
        center_x_px=center_x_px,
        center_y_px=center_y_px,
        center_x_roi_px=estimate.x0_px,
        center_y_roi_px=estimate.y0_px,
        sigma_x_px=estimate.sigma_x_px,
        sigma_y_px=estimate.sigma_y_px,
        sigma_major_px=estimate.sigma_major_px,
        sigma_minor_px=estimate.sigma_minor_px,
        fwhm_x_px=estimate.sigma_x_px * FWHM_PER_SIGMA,
        fwhm_y_px=estimate.sigma_y_px * FWHM_PER_SIGMA,
        fwhm_major_px=estimate.sigma_major_px * FWHM_PER_SIGMA,
        fwhm_minor_px=estimate.sigma_minor_px * FWHM_PER_SIGMA,
        theta_deg=estimate.theta_deg,
        amplitude=estimate.amplitude,
        background_level=estimate.background_level,
        total_intensity=estimate.total_intensity,
        peak_intensity=estimate.peak_intensity,
        fit_success=diagnostics.success,
        fit_rmse=diagnostics.rmse,
        fit_r_squared=diagnostics.r_squared,
        scale_mm_per_px=scale,
        dx_mm=dx_mm,
        dy_mm=dy_mm,
        tilt_x_urad=tilt_x_urad,
        tilt_y_urad=tilt_y_urad,
        radial_tilt_urad=radial_tilt_urad,
        selected_tilt_urad=selected_tilt_urad,
        absolute_tilt_mrad=absolute_tilt_mrad,
        acquisition_fps=acquisition_fps,
    )
    return result, roi_image


def estimate_sample_rate_hz(records: list[FrameAnalysisResult]) -> float:
    """Estimate the effective sampling rate from irregular timestamps."""
    if len(records) < 2:
        return 0.0
    timestamps = np.array([record.timestamp_s for record in records], dtype=np.float64)
    dt = np.diff(timestamps)
    dt = dt[dt > 0.0]
    if dt.size == 0:
        return 0.0
    return float(1.0 / np.median(dt))


def _series_from_records(
    records: list[FrameAnalysisResult],
    axis: str,
) -> np.ndarray:
    if axis == "X":
        return np.array([record.tilt_x_urad for record in records], dtype=np.float64)
    if axis == "Radial":
        return np.array([record.radial_tilt_urad for record in records], dtype=np.float64)
    return np.array([record.tilt_y_urad for record in records], dtype=np.float64)



def compute_session_summary(
    records: list[FrameAnalysisResult],
    axis: str,
    static_tilt_mrad: float,
) -> dict[str, float | int | str]:
    """Aggregate the current session into publication-style summary metrics."""
    if not records:
        return {
            "selected_axis": axis,
            "samples": 0,
            "duration_s": 0.0,
            "sampling_rate_hz": 0.0,
            "mean_tilt_urad": 0.0,
            "std_tilt_urad": 0.0,
            "rms_tilt_urad": 0.0,
            "peak_to_peak_urad": 0.0,
            "drift_slope_urad_per_s": 0.0,
            "mean_absolute_tilt_mrad": static_tilt_mrad,
            "mean_fwhm_major_px": 0.0,
            "mean_fwhm_minor_px": 0.0,
        }

    timestamps = np.array([record.timestamp_s for record in records], dtype=np.float64)
    rel_time = timestamps - timestamps[0]
    series = _series_from_records(records, axis)
    absolute_tilt = np.array(
        [record.absolute_tilt_mrad for record in records],
        dtype=np.float64,
    )
    fwhm_major = np.array([record.fwhm_major_px for record in records], dtype=np.float64)
    fwhm_minor = np.array([record.fwhm_minor_px for record in records], dtype=np.float64)

    slope = 0.0
    if len(records) >= 2 and float(np.ptp(rel_time)) > 0.0:
        slope = float(linregress(rel_time, series).slope)

    return {
        "selected_axis": axis,
        "samples": int(len(records)),
        "duration_s": float(rel_time[-1]) if len(records) > 1 else 0.0,
        "sampling_rate_hz": estimate_sample_rate_hz(records),
        "mean_tilt_urad": float(np.mean(series)),
        "std_tilt_urad": float(np.std(series, ddof=1)) if len(records) > 1 else 0.0,
        "rms_tilt_urad": float(np.sqrt(np.mean(np.square(series)))),
        "peak_to_peak_urad": float(np.ptp(series)),
        "drift_slope_urad_per_s": slope,
        "mean_absolute_tilt_mrad": float(np.mean(absolute_tilt)),
        "mean_fwhm_major_px": float(np.mean(fwhm_major)),
        "mean_fwhm_minor_px": float(np.mean(fwhm_minor)),
    }
