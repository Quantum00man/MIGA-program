"""PyQt5 user interface for Basler beam-tilt measurements."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, replace
from datetime import datetime
import csv
import json
import os
import threading
import traceback
from typing import Any

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Ellipse, Rectangle
import numpy as np
from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from scipy.ndimage import gaussian_filter

from .analysis import (
    AnalysisSettings,
    FrameAnalysisResult,
    GeometrySettings,
    OnlineSessionSummary,
    analyze_frame,
    clipped_roi,
    scale_mm_per_px,
)
from .camera import (
    BaslerCameraBackend,
    CameraBackendError,
    CameraSettings,
    CameraTimeoutError,
    DemoCameraBackend,
)


MAX_GAUSSIAN_REFINEMENT_PIXELS = 250_000
TIME_SERIES_WINDOW_S = 60.0
MAX_TIME_SERIES_POINTS = 4000
DEFAULT_OUTPUT_CSV_NAME = "beam_tilt_session.csv"
SESSION_CSV_FLUSH_INTERVAL = 1


class FrameDisplayPacket:
    """Payload sent from the worker thread to the GUI."""

    def __init__(
        self,
        *,
        timestamp_s: float,
        full_frame: np.ndarray,
        roi_tuple: tuple[int, int, int, int],
        result: FrameAnalysisResult | None,
        acquisition_fps: float,
        analysis_enabled: bool,
    ) -> None:
        self.timestamp_s = timestamp_s
        self.full_frame = full_frame
        self.roi_tuple = roi_tuple
        self.result = result
        self.acquisition_fps = acquisition_fps
        self.analysis_enabled = analysis_enabled


@dataclass(slots=True)
class RecordingPlan:
    sample_interval_s: float
    stop_mode: str
    target_points: int | None
    target_duration_s: float | None
    output_csv_path: str


class LiveImageCanvas(FigureCanvasQTAgg):
    """Matplotlib canvas for live camera preview with in-image X/Y profile overlays."""

    roi_selected = pyqtSignal(int, int, int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        self.figure = Figure(figsize=(7.8, 6.0))
        super().__init__(self.figure)
        self.setParent(parent)
        self.setFocusPolicy(Qt.ClickFocus)

        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Live Camera Preview")
        self.ax.set_xlabel("Pixels")
        self.ax.set_ylabel("Pixels")

        self.image_artist = self.ax.imshow(
            np.zeros((8, 8), dtype=np.float64),
            cmap="viridis",
            origin="lower",
            interpolation="nearest",
        )
        self.center_artist = self.ax.scatter(
            [],
            [],
            marker="+",
            s=90,
            c="white",
            zorder=8,
        )
        self.fwhm_ellipse = Ellipse(
            (0.0, 0.0),
            width=1.0,
            height=1.0,
            angle=0.0,
            fill=False,
            linewidth=1.4,
            edgecolor="white",
            zorder=7,
        )
        self.fwhm_ellipse.set_visible(False)
        self.ax.add_patch(self.fwhm_ellipse)
        self.roi_rect = Rectangle(
            (0.0, 0.0),
            width=1.0,
            height=1.0,
            fill=False,
            linewidth=1.3,
            edgecolor="#ff6f61",
            zorder=9,
        )
        self.ax.add_patch(self.roi_rect)
        self.drag_rect = Rectangle(
            (0.0, 0.0),
            width=1.0,
            height=1.0,
            fill=False,
            linewidth=1.2,
            linestyle="--",
            edgecolor="#ffd166",
            zorder=10,
        )
        self.drag_rect.set_visible(False)
        self.ax.add_patch(self.drag_rect)

        self.profile_x_band = Rectangle(
            (0.0, 0.0),
            width=1.0,
            height=1.0,
            fill=True,
            facecolor="white",
            edgecolor="#1f77b4",
            linewidth=0.8,
            alpha=0.10,
            zorder=4,
        )
        self.profile_y_band = Rectangle(
            (0.0, 0.0),
            width=1.0,
            height=1.0,
            fill=True,
            facecolor="white",
            edgecolor="#ff7f0e",
            linewidth=0.8,
            alpha=0.10,
            zorder=4,
        )
        self.profile_x_band.set_visible(False)
        self.profile_y_band.set_visible(False)
        self.ax.add_patch(self.profile_x_band)
        self.ax.add_patch(self.profile_y_band)

        self.profile_x_line, = self.ax.plot([], [], color="#1f77b4", linewidth=1.4, zorder=5)
        self.profile_y_line, = self.ax.plot([], [], color="#ff7f0e", linewidth=1.4, zorder=5)
        self.profile_x_center_line, = self.ax.plot([], [], color="#ff6f61", linewidth=1.0, zorder=6)
        self.profile_y_center_line, = self.ax.plot([], [], color="#ff6f61", linewidth=1.0, zorder=6)
        self.profile_x_line.set_visible(False)
        self.profile_y_line.set_visible(False)
        self.profile_x_center_line.set_visible(False)
        self.profile_y_center_line.set_visible(False)

        self._frame_shape = (8, 8)
        self._display_counter = 0
        self._cached_clim = (0.0, 1.0)
        self._force_contrast_refresh = True
        self._contrast_mode = "Auto"
        self._contrast_refresh_frames = 10
        self._show_profiles = True
        self._profile_refresh_hz = 2.0
        self._profile_max_points = 256
        self._last_profile_update_s: float | None = None
        self._last_profile_roi_tuple: tuple[int, int, int, int] | None = None
        self._last_title: str | None = None
        self._drag_origin_px: tuple[float, float] | None = None
        self._drag_current_px: tuple[float, float] | None = None

        self.mpl_connect("button_press_event", self._on_mouse_press)
        self.mpl_connect("motion_notify_event", self._on_mouse_move)
        self.mpl_connect("button_release_event", self._on_mouse_release)

    def configure_display(
        self,
        *,
        show_profiles: bool,
        profile_refresh_hz: float,
        profile_max_points: int,
        contrast_mode: str,
        contrast_refresh_frames: int,
    ) -> None:
        self._show_profiles = bool(show_profiles)
        self._profile_refresh_hz = max(float(profile_refresh_hz), 0.1)
        self._profile_max_points = max(32, int(profile_max_points))
        self._contrast_mode = contrast_mode
        self._contrast_refresh_frames = max(1, int(contrast_refresh_frames))
        self._force_contrast_refresh = True
        self._last_profile_update_s = None
        self._last_profile_roi_tuple = None
        if not self._show_profiles:
            self._hide_profile_overlay()

    def request_contrast_refresh(self) -> None:
        self._force_contrast_refresh = True

    def _clip_point_to_frame(self, x: float, y: float) -> tuple[float, float]:
        frame_height, frame_width = self._frame_shape
        clipped_x = min(max(float(x), 0.0), max(frame_width - 1, 0))
        clipped_y = min(max(float(y), 0.0), max(frame_height - 1, 0))
        return clipped_x, clipped_y

    def _update_drag_rect(self) -> None:
        if self._drag_origin_px is None or self._drag_current_px is None:
            self.drag_rect.set_visible(False)
            return

        x0, y0 = self._drag_origin_px
        x1, y1 = self._drag_current_px
        x_min = min(x0, x1)
        y_min = min(y0, y1)
        width = max(abs(x1 - x0), 1.0)
        height = max(abs(y1 - y0), 1.0)
        self.drag_rect.set_xy((x_min, y_min))
        self.drag_rect.set_width(width)
        self.drag_rect.set_height(height)
        self.drag_rect.set_visible(True)

    def _clear_drag_rect(self) -> None:
        self._drag_origin_px = None
        self._drag_current_px = None
        self.drag_rect.set_visible(False)

    def _selection_from_drag(self) -> tuple[int, int, int, int] | None:
        if self._drag_origin_px is None or self._drag_current_px is None:
            return None

        x0, y0 = self._drag_origin_px
        x1, y1 = self._drag_current_px
        x_min = int(np.floor(min(x0, x1)))
        y_min = int(np.floor(min(y0, y1)))
        x_max = int(np.ceil(max(x0, x1))) + 1
        y_max = int(np.ceil(max(y0, y1))) + 1

        frame_height, frame_width = self._frame_shape
        x_min = min(max(x_min, 0), max(frame_width - 1, 0))
        y_min = min(max(y_min, 0), max(frame_height - 1, 0))
        x_max = min(max(x_max, x_min + 1), frame_width)
        y_max = min(max(y_max, y_min + 1), frame_height)
        return x_min, y_min, x_max - x_min, y_max - y_min

    def _on_mouse_press(self, event) -> None:
        if event.button != 1 or event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            return
        self._drag_origin_px = self._clip_point_to_frame(event.xdata, event.ydata)
        self._drag_current_px = self._drag_origin_px
        self._update_drag_rect()
        self.draw_idle()

    def _on_mouse_move(self, event) -> None:
        if self._drag_origin_px is None or event.xdata is None or event.ydata is None:
            return
        self._drag_current_px = self._clip_point_to_frame(event.xdata, event.ydata)
        self._update_drag_rect()
        self.draw_idle()

    def _on_mouse_release(self, event) -> None:
        if self._drag_origin_px is None:
            return
        if event.xdata is not None and event.ydata is not None:
            self._drag_current_px = self._clip_point_to_frame(event.xdata, event.ydata)
        selection = self._selection_from_drag()
        self._clear_drag_rect()
        self.draw_idle()
        if selection is None:
            return
        roi_x, roi_y, roi_width, roi_height = selection
        if roi_width < 2 or roi_height < 2:
            return
        self.roi_selected.emit(roi_x, roi_y, roi_width, roi_height)

    @staticmethod
    def _downsample_profile(
        coords: np.ndarray,
        profile: np.ndarray,
        max_points: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        if profile.size <= max_points:
            return coords, profile

        edges = np.linspace(0, profile.size, max_points + 1, dtype=int)
        downsampled_coords = np.empty(max_points, dtype=np.float64)
        downsampled_profile = np.empty(max_points, dtype=np.float64)
        for idx in range(max_points):
            start = edges[idx]
            stop = edges[idx + 1]
            if stop <= start:
                stop = min(start + 1, profile.size)
            downsampled_coords[idx] = float(np.mean(coords[start:stop]))
            downsampled_profile[idx] = float(np.mean(profile[start:stop]))
        return downsampled_coords, downsampled_profile

    @staticmethod
    def _normalize_profile(profile: np.ndarray) -> np.ndarray:
        profile_min = float(np.min(profile))
        profile_max = float(np.max(profile))
        span = profile_max - profile_min
        if not np.isfinite(span) or span <= 1.0e-12:
            return np.full_like(profile, 0.5, dtype=np.float64)
        return (profile - profile_min) / span

    @staticmethod
    def _profile_band_sizes(frame_width: int, frame_height: int) -> tuple[float, float]:
        band_height = min(max(frame_height * 0.14, 36.0), 110.0)
        band_width = min(max(frame_width * 0.14, 36.0), 140.0)
        return float(band_height), float(band_width)

    def _hide_profile_overlay(self) -> None:
        self.profile_x_band.set_visible(False)
        self.profile_y_band.set_visible(False)
        self.profile_x_line.set_visible(False)
        self.profile_y_line.set_visible(False)
        self.profile_x_center_line.set_visible(False)
        self.profile_y_center_line.set_visible(False)
        self.profile_x_line.set_data([], [])
        self.profile_y_line.set_data([], [])

    def _update_contrast_limits(self, display_image: np.ndarray) -> None:
        should_refresh = self._force_contrast_refresh
        if not should_refresh and self._contrast_mode == "Auto":
            should_refresh = self._display_counter % self._contrast_refresh_frames == 0

        if should_refresh:
            frame_height, frame_width = display_image.shape
            sample_stride = 1
            longest_edge = max(frame_height, frame_width)
            if longest_edge > 1500:
                sample_stride = 4
            elif longest_edge > 900:
                sample_stride = 2
            sample = display_image[::sample_stride, ::sample_stride]
            low = float(np.percentile(sample, 2.0))
            high = float(np.percentile(sample, 99.8))
            if not np.isfinite(low) or not np.isfinite(high) or low == high:
                low = float(np.min(sample))
                high = float(np.max(sample) + 1.0)
            self._cached_clim = (low, high)
            self._force_contrast_refresh = False

        self.image_artist.set_clim(*self._cached_clim)

    def _update_profile_overlay(
        self,
        roi_view: np.ndarray,
        roi_tuple: tuple[int, int, int, int],
        result: FrameAnalysisResult | None,
        analysis_enabled: bool,
        timestamp_s: float,
    ) -> None:
        frame_height, frame_width = self._frame_shape
        x_band_height, y_band_width = self._profile_band_sizes(frame_width, frame_height)
        x_band_height = min(x_band_height, max(frame_height - 1, 1.0))
        y_band_width = min(y_band_width, max(frame_width - 1, 1.0))
        y_band_x0 = max(frame_width - y_band_width, 0.0)

        if not self._show_profiles or roi_view.size == 0:
            self._hide_profile_overlay()
            return

        self.profile_x_band.set_xy((0.0, 0.0))
        self.profile_x_band.set_width(max(frame_width - 1, 1.0))
        self.profile_x_band.set_height(x_band_height)
        self.profile_x_band.set_visible(True)

        self.profile_y_band.set_xy((y_band_x0, 0.0))
        self.profile_y_band.set_width(y_band_width)
        self.profile_y_band.set_height(max(frame_height - 1, 1.0))
        self.profile_y_band.set_visible(True)

        refresh_interval_s = 1.0 / max(self._profile_refresh_hz, 0.1)
        should_refresh_profiles = (
            self._last_profile_update_s is None
            or timestamp_s - self._last_profile_update_s >= refresh_interval_s
            or self._last_profile_roi_tuple != roi_tuple
        )

        if should_refresh_profiles:
            roi_x, roi_y, roi_width, roi_height = roi_tuple
            x_coords = np.arange(roi_x, roi_x + roi_width, dtype=np.float64)
            y_coords = np.arange(roi_y, roi_y + roi_height, dtype=np.float64)
            x_profile = np.mean(roi_view, axis=0)
            y_profile = np.mean(roi_view, axis=1)

            x_coords, x_profile = self._downsample_profile(
                x_coords,
                x_profile,
                self._profile_max_points,
            )
            y_coords, y_profile = self._downsample_profile(
                y_coords,
                y_profile,
                self._profile_max_points,
            )

            x_norm = self._normalize_profile(x_profile)
            y_norm = self._normalize_profile(y_profile)
            x_padding = min(6.0, max(x_band_height * 0.15, 3.0))
            y_padding = min(6.0, max(y_band_width * 0.15, 3.0))
            x_plot_y = x_padding + x_norm * max(x_band_height - 2.0 * x_padding, 1.0)
            y_plot_x = y_band_x0 + y_padding + y_norm * max(y_band_width - 2.0 * y_padding, 1.0)

            self.profile_x_line.set_data(x_coords, x_plot_y)
            self.profile_y_line.set_data(y_plot_x, y_coords)
            self.profile_x_line.set_visible(True)
            self.profile_y_line.set_visible(True)
            self._last_profile_update_s = timestamp_s
            self._last_profile_roi_tuple = roi_tuple

        if analysis_enabled and result is not None and self.profile_x_line.get_visible():
            self.profile_x_center_line.set_data(
                [result.center_x_px, result.center_x_px],
                [0.0, x_band_height],
            )
            self.profile_y_center_line.set_data(
                [y_band_x0, y_band_x0 + y_band_width],
                [result.center_y_px, result.center_y_px],
            )
            self.profile_x_center_line.set_visible(True)
            self.profile_y_center_line.set_visible(True)
        else:
            self.profile_x_center_line.set_visible(False)
            self.profile_y_center_line.set_visible(False)

    def update_view(
        self,
        frame_image: np.ndarray,
        roi_tuple: tuple[int, int, int, int],
        result: FrameAnalysisResult | None,
        analysis_enabled: bool,
        subtract_background: bool,
        timestamp_s: float,
    ) -> None:
        display_image = frame_image.astype(np.float64, copy=False)
        frame_height, frame_width = display_image.shape
        self._display_counter += 1

        shape_changed = (frame_height, frame_width) != self._frame_shape
        self._frame_shape = (frame_height, frame_width)
        self.image_artist.set_data(display_image)
        if shape_changed:
            self.image_artist.set_extent((-0.5, frame_width - 0.5, -0.5, frame_height - 0.5))
            self.ax.set_xlim(0.0, max(frame_width - 1, 1))
            self.ax.set_ylim(0.0, max(frame_height - 1, 1))
            self._force_contrast_refresh = True
            self._last_profile_update_s = None
            self._last_profile_roi_tuple = None

        self._update_contrast_limits(display_image)

        roi_x, roi_y, roi_width, roi_height = roi_tuple
        self.roi_rect.set_xy((roi_x, roi_y))
        self.roi_rect.set_width(max(roi_width, 1.0))
        self.roi_rect.set_height(max(roi_height, 1.0))
        self.roi_rect.set_visible(True)

        roi_view = display_image[roi_y:roi_y + roi_height, roi_x:roi_x + roi_width]
        self._update_profile_overlay(
            roi_view,
            roi_tuple,
            result,
            analysis_enabled,
            timestamp_s,
        )

        if analysis_enabled and result is not None:
            self.center_artist.set_offsets(
                np.array([[result.center_x_px, result.center_y_px]], dtype=np.float64)
            )
            self.fwhm_ellipse.center = (result.center_x_px, result.center_y_px)
            self.fwhm_ellipse.width = max(result.fwhm_major_px, 1.0)
            self.fwhm_ellipse.height = max(result.fwhm_minor_px, 1.0)
            self.fwhm_ellipse.angle = result.theta_deg
            self.fwhm_ellipse.set_visible(True)
        else:
            self.center_artist.set_offsets(np.empty((0, 2)))
            self.fwhm_ellipse.set_visible(False)

        mode_text = "Analysis running" if analysis_enabled else "Preview only"
        title = (
            f"Live Camera Preview | {mode_text} | "
            f"ROI [{roi_x}:{roi_x + roi_width}, {roi_y}:{roi_y + roi_height}]"
        )
        if self._show_profiles:
            title += (
                f" | XY overlay {self._profile_refresh_hz:.1f} Hz"
                f" | {self._profile_max_points} pts"
            )
        if subtract_background and analysis_enabled:
            title += " | Background-subtracted analysis"
        if title != self._last_title:
            self.ax.set_title(title)
            self._last_title = title
        self.draw_idle()


class TimeSeriesCanvas(FigureCanvasQTAgg):
    """Live time-domain tilt plot."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self.figure = Figure(figsize=(7.0, 3.2), constrained_layout=True)
        super().__init__(self.figure)
        self.setParent(parent)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Tilt Time Series")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Tilt jitter (urad)")
        self.line_x, = self.ax.plot([], [], label="X", linewidth=1.3)
        self.line_y, = self.ax.plot([], [], label="Y", linewidth=1.3)
        self.line_r, = self.ax.plot([], [], label="Radial", linewidth=1.3)
        self.ax.legend(loc="upper right")

    @staticmethod
    def _downsample_indices(point_count: int, max_points: int) -> np.ndarray:
        if point_count <= max_points:
            return np.arange(point_count, dtype=int)
        step = int(np.ceil(point_count / max_points))
        indices = np.arange(0, point_count, step, dtype=int)
        if indices[-1] != point_count - 1:
            indices = np.append(indices, point_count - 1)
        return indices

    def update_view(
        self,
        records: list[FrameAnalysisResult],
        window_s: float = TIME_SERIES_WINDOW_S,
        max_points: int = MAX_TIME_SERIES_POINTS,
    ) -> None:
        if not records:
            for line in (self.line_x, self.line_y, self.line_r):
                line.set_data([], [])
            self.ax.relim()
            self.ax.autoscale_view()
            self.draw_idle()
            return

        time_axis = np.fromiter((record.timestamp_s for record in records), dtype=np.float64, count=len(records))
        time_axis = time_axis - time_axis[0]
        if time_axis[-1] > window_s:
            cutoff = time_axis[-1] - window_s
            start_idx = int(np.searchsorted(time_axis, cutoff, side="left"))
            records = records[start_idx:]
            time_axis = time_axis[start_idx:]
            time_axis = time_axis - time_axis[0]

        x = np.fromiter((record.tilt_x_urad for record in records), dtype=np.float64, count=len(records))
        y = np.fromiter((record.tilt_y_urad for record in records), dtype=np.float64, count=len(records))
        radial = np.fromiter((record.radial_tilt_urad for record in records), dtype=np.float64, count=len(records))

        indices = self._downsample_indices(time_axis.size, max_points)
        if indices.size != time_axis.size:
            time_axis = time_axis[indices]
            x = x[indices]
            y = y[indices]
            radial = radial[indices]

        self.line_x.set_data(time_axis, x)
        self.line_y.set_data(time_axis, y)
        self.line_r.set_data(time_axis, radial)
        self.ax.relim()
        self.ax.autoscale_view()
        self.draw_idle()


class RulerCalibrationDialog(QDialog):
    """Interactive calibration dialog using a ruler visible in the preview frame."""

    def __init__(self, frame_image: np.ndarray, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ruler Calibration")
        self.resize(1100, 760)
        self._frame_image = frame_image.astype(np.float64, copy=False)
        self._points: list[tuple[float, float]] = []

        self.figure = Figure(figsize=(8.5, 5.8), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Click two ruler marks on the preview image")
        self.ax.set_xlabel("Pixels")
        self.ax.set_ylabel("Pixels")

        self.image_artist = self.ax.imshow(
            self._frame_image,
            cmap="viridis",
            origin="lower",
            interpolation="nearest",
        )
        self.selection_artist, = self.ax.plot([], [], "o-", color="#ff6f61", linewidth=1.8)

        low = float(np.percentile(self._frame_image, 2.0))
        high = float(np.percentile(self._frame_image, 99.8))
        if not np.isfinite(low) or not np.isfinite(high) or low == high:
            low = float(np.min(self._frame_image))
            high = float(np.max(self._frame_image) + 1.0)
        frame_height, frame_width = self._frame_image.shape
        self.image_artist.set_clim(low, high)
        self.image_artist.set_extent((-0.5, frame_width - 0.5, -0.5, frame_height - 0.5))
        self.ax.set_xlim(0.0, max(frame_width - 1, 1))
        self.ax.set_ylim(0.0, max(frame_height - 1, 1))

        instructions = QLabel(
            "Instructions: click two ruler marks in the preview image. Enter the real distance between those marks, then press OK to use the computed manual scale."
        )
        instructions.setWordWrap(True)

        self.length_spin = QDoubleSpinBox()
        self.length_spin.setRange(0.001, 1_000_000.0)
        self.length_spin.setDecimals(4)
        self.length_spin.setValue(10.0)
        self.length_spin.setSuffix(" ")
        self.length_spin.valueChanged.connect(self._update_metrics)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["mm", "cm"])
        self.unit_combo.currentIndexChanged.connect(self._update_metrics)

        self.pixel_distance_label = QLabel("Select two points")
        self.scale_label = QLabel("-")

        reset_button = QPushButton("Reset Points")
        reset_button.clicked.connect(self._reset_points)

        form = QFormLayout()
        length_row = QWidget()
        length_layout = QHBoxLayout(length_row)
        length_layout.setContentsMargins(0, 0, 0, 0)
        length_layout.addWidget(self.length_spin)
        length_layout.addWidget(self.unit_combo)
        form.addRow("Known length", length_row)
        form.addRow("Pixel distance", self.pixel_distance_label)
        form.addRow("Computed scale", self.scale_label)
        form.addRow("Selection", reset_button)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)

        layout = QVBoxLayout(self)
        layout.addWidget(instructions)
        layout.addWidget(self.canvas, stretch=1)
        layout.addLayout(form)
        layout.addWidget(self.button_box)

        self.canvas.mpl_connect("button_press_event", self._handle_click)
        self._update_metrics()

    def _handle_click(self, event) -> None:
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            return
        point = (float(event.xdata), float(event.ydata))
        if len(self._points) >= 2:
            self._points = [point]
        else:
            self._points.append(point)
        self._update_metrics()

    def _reset_points(self) -> None:
        self._points.clear()
        self._update_metrics()

    def _known_length_mm(self) -> float:
        multiplier = 10.0 if self.unit_combo.currentText() == "cm" else 1.0
        return self.length_spin.value() * multiplier

    def selected_scale_mm_per_px(self) -> float | None:
        if len(self._points) != 2:
            return None
        pixel_distance = float(np.hypot(
            self._points[1][0] - self._points[0][0],
            self._points[1][1] - self._points[0][1],
        ))
        if pixel_distance <= 0.0:
            return None
        return self._known_length_mm() / pixel_distance

    def _update_metrics(self) -> None:
        if not self._points:
            self.selection_artist.set_data([], [])
        else:
            xs = [point[0] for point in self._points]
            ys = [point[1] for point in self._points]
            self.selection_artist.set_data(xs, ys)
        self.canvas.draw_idle()

        scale = self.selected_scale_mm_per_px()
        if len(self._points) == 2:
            pixel_distance = float(np.hypot(
                self._points[1][0] - self._points[0][0],
                self._points[1][1] - self._points[0][1],
            ))
            self.pixel_distance_label.setText(f"{pixel_distance:.3f} px")
        elif len(self._points) == 1:
            self.pixel_distance_label.setText("Select the second point")
        else:
            self.pixel_distance_label.setText("Select two points")

        if scale is None:
            self.scale_label.setText("-")
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
        else:
            self.scale_label.setText(f"{scale:.6f} mm/px")
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)


class AcquisitionWorker(QThread):
    """Worker thread that owns the camera backend and live analysis loop."""

    frame_available = pyqtSignal()
    analysis_result = pyqtSignal(object)
    status_message = pyqtSignal(str)
    error_message = pyqtSignal(str)
    connected_message = pyqtSignal(str)
    applied_camera_settings = pyqtSignal(object)
    analysis_state_changed = pyqtSignal(bool)

    def __init__(
        self,
        backend_name: str,
        camera_settings: CameraSettings,
        geometry_settings: GeometrySettings,
        analysis_settings: AnalysisSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.backend_name = backend_name
        self._camera_settings = camera_settings
        self._geometry_settings = geometry_settings
        self._analysis_settings = analysis_settings
        self._background_frame: np.ndarray | None = None
        self._background_target = 0
        self._background_remaining = 0
        self._background_accumulator: np.ndarray | None = None
        self._reference_center_px: tuple[float, float] | None = None
        self._reset_reference_requested = True
        self._stop_requested = False
        self._pending_camera_apply = False
        self._last_result: FrameAnalysisResult | None = None
        self._backend = None
        self._analysis_enabled = False
        self._large_roi_warning_emitted = False
        self._consecutive_timeouts = 0
        self._display_packet_lock = threading.Lock()
        self._latest_display_packet: FrameDisplayPacket | None = None
        self._frame_notification_pending = False
        self._last_analysis_emit_s: float | None = None

    def stop(self) -> None:
        self._stop_requested = True

    def start_analysis(self) -> None:
        self._analysis_enabled = True
        self._reset_reference_requested = True
        self._last_result = None
        self._last_analysis_emit_s = None
        self.analysis_state_changed.emit(True)
        self.status_message.emit(
            "Analysis started. The next valid fitted frame will define the reference center."
        )

    def stop_analysis(self) -> None:
        if not self._analysis_enabled:
            return
        self._analysis_enabled = False
        self._last_result = None
        self._last_analysis_emit_s = None
        self.analysis_state_changed.emit(False)
        self.status_message.emit("Analysis stopped. Live preview remains active.")

    def update_camera_settings(self, settings: CameraSettings) -> None:
        self._camera_settings = settings
        self._pending_camera_apply = True
        self._consecutive_timeouts = 0
        self._last_analysis_emit_s = None

    def update_geometry_settings(self, settings: GeometrySettings) -> None:
        self._geometry_settings = settings

    def update_analysis_settings(self, settings: AnalysisSettings) -> None:
        self._analysis_settings = settings
        self._large_roi_warning_emitted = False

    def request_reference_reset(self) -> None:
        self._reset_reference_requested = True

    def request_background_capture(self, frame_count: int) -> None:
        frame_count = max(1, int(frame_count))
        self._background_target = frame_count
        self._background_remaining = frame_count
        self._background_accumulator = None
        self.status_message.emit(
            f"Capturing background: average of {frame_count} frames. Block the beam during this step."
        )

    def clear_background(self) -> None:
        self._background_frame = None
        self.status_message.emit("Background frame cleared.")

    def take_latest_display_packet(self) -> FrameDisplayPacket | None:
        with self._display_packet_lock:
            packet = self._latest_display_packet
            self._latest_display_packet = None
            self._frame_notification_pending = False
        return packet

    def _publish_display_packet(self, packet: FrameDisplayPacket) -> None:
        should_emit = False
        with self._display_packet_lock:
            self._latest_display_packet = packet
            if not self._frame_notification_pending:
                self._frame_notification_pending = True
                should_emit = True
        if should_emit:
            self.frame_available.emit()

    def _frame_timeout_ms(self) -> int:
        frame_rate_fps = max(self._camera_settings.frame_rate_fps, 0.1)
        frame_period_ms = 1000.0 / frame_rate_fps
        exposure_ms = max(self._camera_settings.exposure_us / 1000.0, 0.0)
        timeout_ms = max(1000.0, 3.0 * frame_period_ms + exposure_ms + 500.0)
        return int(min(timeout_ms, 15000.0))

    def _effective_analysis_settings(self) -> AnalysisSettings:
        roi_pixels = max(1, int(self._analysis_settings.roi_width) * int(self._analysis_settings.roi_height))
        if self._analysis_settings.gaussian_refinement and roi_pixels > MAX_GAUSSIAN_REFINEMENT_PIXELS:
            if not self._large_roi_warning_emitted:
                self.status_message.emit(
                    "Gaussian refinement disabled for large ROI to keep live analysis responsive. Reduce ROI size to restore full 2D fitting."
                )
                self._large_roi_warning_emitted = True
            return replace(self._analysis_settings, gaussian_refinement=False)
        self._large_roi_warning_emitted = False
        return self._analysis_settings

    def _create_backend(self):
        if self.backend_name == "Basler":
            return BaslerCameraBackend()
        return DemoCameraBackend()

    def run(self) -> None:
        try:
            self._backend = self._create_backend()
            description = self._backend.connect(self._camera_settings.serial_number)
            self.connected_message.emit(description)
            applied = self._backend.apply_settings(self._camera_settings)
            self.applied_camera_settings.emit(applied)
            self._camera_settings = applied
            self._background_frame = None
            self._last_analysis_emit_s = None
            self._backend.start_grabbing()
            self.analysis_state_changed.emit(False)
            self.status_message.emit("Preview started. Adjust the camera, then click Start Analysis.")

            fps_counter = 0
            fps_timer_s = 0.0
            acquisition_fps = 0.0
            last_display_emit_s = 0.0

            while not self._stop_requested:
                if self._pending_camera_apply:
                    self._backend.stop_grabbing()
                    applied = self._backend.apply_settings(self._camera_settings)
                    self._camera_settings = applied
                    self.applied_camera_settings.emit(applied)
                    self._background_frame = None
                    self._background_accumulator = None
                    self._background_remaining = 0
                    self._last_result = None
                    self._last_analysis_emit_s = None
                    self._backend.start_grabbing()
                    self._pending_camera_apply = False
                    self._consecutive_timeouts = 0
                    self.status_message.emit("Camera settings applied.")

                timeout_ms = self._frame_timeout_ms()
                try:
                    packet = self._backend.retrieve_frame(timeout_ms=timeout_ms)
                    self._consecutive_timeouts = 0
                except CameraTimeoutError:
                    self._consecutive_timeouts += 1
                    if self._stop_requested:
                        break
                    if self._consecutive_timeouts <= 3:
                        self.status_message.emit(
                            f"No frame arrived within {timeout_ms} ms. Waiting for the camera stream..."
                        )
                        continue
                    raise
                fps_counter += 1
                if fps_timer_s == 0.0:
                    fps_timer_s = packet.timestamp_s
                elapsed_for_fps = packet.timestamp_s - fps_timer_s
                if elapsed_for_fps >= 1.0:
                    acquisition_fps = fps_counter / max(elapsed_for_fps, 1.0e-9)
                    fps_counter = 0
                    fps_timer_s = packet.timestamp_s

                if self._background_remaining > 0:
                    frame_float = packet.image.astype(np.float64, copy=False)
                    if (
                        self._background_accumulator is None
                        or self._background_accumulator.shape != frame_float.shape
                    ):
                        self._background_accumulator = np.zeros_like(frame_float)
                    self._background_accumulator += frame_float
                    self._background_remaining -= 1
                    if self._background_remaining == 0 and self._background_accumulator is not None:
                        self._background_frame = (
                            self._background_accumulator / float(self._background_target)
                        )
                        self.status_message.emit(
                            f"Background captured from {self._background_target} frames."
                        )

                effective_analysis_settings = self._effective_analysis_settings()
                roi_slice_y, roi_slice_x, roi_tuple = clipped_roi(
                    packet.image.shape,
                    effective_analysis_settings.roi_x,
                    effective_analysis_settings.roi_y,
                    effective_analysis_settings.roi_width,
                    effective_analysis_settings.roi_height,
                )
                _ = packet.image[roi_slice_y, roi_slice_x]
                result = None

                stride = max(1, int(self._analysis_settings.analysis_stride))
                sample_interval_s = max(float(self._analysis_settings.sample_interval_s), 1.0e-6)
                stride_ok = packet.frame_index % stride == 0
                interval_ok = (
                    self._last_analysis_emit_s is None
                    or packet.timestamp_s - self._last_analysis_emit_s >= sample_interval_s - 1.0e-9
                )
                if self._analysis_enabled and stride_ok and interval_ok:
                    current_reference = (
                        None if self._reset_reference_requested else self._reference_center_px
                    )
                    result, _ = analyze_frame(
                        packet.image,
                        packet.timestamp_s,
                        packet.frame_index,
                        self._geometry_settings,
                        effective_analysis_settings,
                        self._background_frame,
                        current_reference,
                        acquisition_fps,
                    )
                    if result is not None:
                        if self._reset_reference_requested or self._reference_center_px is None:
                            self._reference_center_px = (
                                result.center_x_px,
                                result.center_y_px,
                            )
                            self._reset_reference_requested = False
                            self.status_message.emit("Reference center updated.")
                        self._last_result = result
                        self._last_analysis_emit_s = result.timestamp_s
                        self.analysis_result.emit(result)

                display_interval_s = 1.0 / max(self._analysis_settings.display_fps, 1.0)
                if packet.timestamp_s - last_display_emit_s >= display_interval_s:
                    display_result = self._last_result if self._analysis_enabled else None
                    display_packet = FrameDisplayPacket(
                        timestamp_s=packet.timestamp_s,
                        full_frame=packet.image.copy(),
                        roi_tuple=roi_tuple,
                        result=display_result,
                        acquisition_fps=acquisition_fps,
                        analysis_enabled=self._analysis_enabled,
                    )
                    self._publish_display_packet(display_packet)
                    last_display_emit_s = packet.timestamp_s

            self.status_message.emit("Preview stopped.")
        except CameraBackendError as exc:
            self.error_message.emit(str(exc))
        except Exception as exc:  # pragma: no cover - GUI error path
            tb = traceback.format_exc()
            self.error_message.emit(f"{exc}\n{tb}")
        finally:
            if self._backend is not None:
                try:
                    self._backend.stop_grabbing()
                except Exception:
                    pass
                try:
                    self._backend.disconnect()
                except Exception:
                    pass


class MainWindow(QMainWindow):
    """Main desktop application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Beam Tilt Noise Analyzer")
        self.resize(1600, 980)

        self.worker: AcquisitionWorker | None = None
        self.records: deque[FrameAnalysisResult] = deque()
        self.record_count = 0
        self.session_summary = OnlineSessionSummary()
        self.last_display_packet: FrameDisplayPacket | None = None
        self.last_result: FrameAnalysisResult | None = None
        self.last_plot_refresh_s = 0.0
        self.preview_running = False
        self.analysis_running = False
        self._session_csv_handle = None
        self._session_csv_writer = None
        self._session_csv_temp_path: str | None = None
        self._session_zero_time_s: float | None = None
        self._session_csv_pending_rows = 0
        self._active_stop_mode = "Manual Stop"
        self._active_target_points: int | None = None
        self._active_target_duration_s: float | None = None

        self.live_canvas = LiveImageCanvas()
        self.time_series_canvas = TimeSeriesCanvas()
        self.live_canvas.roi_selected.connect(self.on_canvas_roi_selected)

        self._build_ui()
        self.apply_display_preferences()
        self._refresh_scale_hint()
        self._update_summary_text()
        self._set_analysis_metrics_placeholder("Preview not started")
        self._sync_control_states()

    def _build_ui(self) -> None:
        central_widget = QWidget()
        central_layout = QHBoxLayout(central_widget)
        central_layout.setContentsMargins(8, 8, 8, 8)

        control_panel = self._build_control_panel()
        visual_panel = self._build_visual_panel()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(control_panel)
        splitter.addWidget(visual_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        central_layout.addWidget(splitter)
        self.setCentralWidget(central_widget)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.statusBar().showMessage("Ready.")

    def _build_control_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setAlignment(Qt.AlignTop)

        scroll_layout.addWidget(self._build_acquisition_group())
        scroll_layout.addWidget(self._build_geometry_group())
        scroll_layout.addWidget(self._build_analysis_group())
        scroll_layout.addWidget(self._build_recording_group())
        scroll_layout.addWidget(self._build_session_group())
        scroll_layout.addWidget(self._build_metrics_group())

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        container.setMaximumWidth(500)
        return container

    def _build_visual_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        layout.addWidget(self.live_canvas, stretch=3)

        tabs = QTabWidget()
        time_tab = QWidget()
        time_layout = QVBoxLayout(time_tab)
        time_layout.addWidget(self.time_series_canvas)
        tabs.addTab(time_tab, "Time Series")

        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        summary_layout.addWidget(self.summary_text)
        tabs.addTab(summary_tab, "Summary")

        layout.addWidget(tabs, stretch=2)
        return panel

    def _build_acquisition_group(self) -> QGroupBox:
        group = QGroupBox("Acquisition")
        layout = QGridLayout(group)

        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["Demo", "Basler"])
        self.serial_edit = QLineEdit()
        self.serial_edit.setPlaceholderText("Optional serial number")

        self.exposure_spin = self._make_float_spin(10.0, 1_000_000.0, 5000.0, decimals=1)
        self.gain_spin = self._make_float_spin(0.0, 48.0, 0.0, decimals=2)
        self.frame_rate_spin = self._make_float_spin(0.5, 500.0, 30.0, decimals=2)
        self.pixel_format_combo = QComboBox()
        self.pixel_format_combo.addItems(["Mono8", "Mono12"])

        self.width_spin = self._make_int_spin(16, 4096, 1440)
        self.height_spin = self._make_int_spin(16, 4096, 1080)
        self.offset_x_spin = self._make_int_spin(0, 4096, 0)
        self.offset_y_spin = self._make_int_spin(0, 4096, 0)

        self.connect_preview_button = QPushButton("Connect Preview")
        self.disconnect_button = QPushButton("Disconnect")
        self.start_analysis_button = QPushButton("Start Analysis")
        self.stop_analysis_button = QPushButton("Stop Analysis")
        self.apply_camera_button = QPushButton("Apply Camera Settings")

        self.connect_preview_button.clicked.connect(self.start_preview)
        self.disconnect_button.clicked.connect(self.disconnect_camera)
        self.start_analysis_button.clicked.connect(self.start_analysis)
        self.stop_analysis_button.clicked.connect(self.stop_analysis)
        self.apply_camera_button.clicked.connect(self.apply_live_settings)

        layout.addWidget(QLabel("Backend"), 0, 0)
        layout.addWidget(self.backend_combo, 0, 1)
        layout.addWidget(QLabel("Serial"), 1, 0)
        layout.addWidget(self.serial_edit, 1, 1)
        layout.addWidget(QLabel("Exposure (us)"), 2, 0)
        layout.addWidget(self.exposure_spin, 2, 1)
        layout.addWidget(QLabel("Gain (dB)"), 3, 0)
        layout.addWidget(self.gain_spin, 3, 1)
        layout.addWidget(QLabel("Frame rate (fps)"), 4, 0)
        layout.addWidget(self.frame_rate_spin, 4, 1)
        layout.addWidget(QLabel("Pixel format"), 5, 0)
        layout.addWidget(self.pixel_format_combo, 5, 1)
        layout.addWidget(QLabel("Width"), 6, 0)
        layout.addWidget(self.width_spin, 6, 1)
        layout.addWidget(QLabel("Height"), 7, 0)
        layout.addWidget(self.height_spin, 7, 1)
        layout.addWidget(QLabel("Offset X"), 8, 0)
        layout.addWidget(self.offset_x_spin, 8, 1)
        layout.addWidget(QLabel("Offset Y"), 9, 0)
        layout.addWidget(self.offset_y_spin, 9, 1)
        layout.addWidget(self.connect_preview_button, 10, 0)
        layout.addWidget(self.disconnect_button, 10, 1)
        layout.addWidget(self.start_analysis_button, 11, 0)
        layout.addWidget(self.stop_analysis_button, 11, 1)
        layout.addWidget(self.apply_camera_button, 12, 0, 1, 2)
        return group

    def _build_geometry_group(self) -> QGroupBox:
        group = QGroupBox("Geometry and Calibration")
        layout = QFormLayout(group)

        self.optical_path_spin = self._make_float_spin(0.01, 1000.0, 10.0, decimals=4)
        self.camera_distance_spin = self._make_float_spin(0.03, 10.0, 0.25, decimals=4)
        self.focal_length_spin = self._make_float_spin(1.0, 500.0, 25.0, decimals=3)
        self.pixel_size_spin = self._make_float_spin(0.1, 20.0, 3.45, decimals=3)
        self.static_tilt_spin = self._make_float_spin(-100.0, 100.0, 1.28, decimals=4)
        self.scale_mode_combo = QComboBox()
        self.scale_mode_combo.addItems(["Thin-lens estimate", "Manual calibration"])
        self.manual_scale_spin = self._make_float_spin(0.0001, 10.0, 0.031, decimals=6)
        self.scale_hint_label = QLabel()
        self.scale_hint_label.setWordWrap(True)
        self.calibrate_scale_button = QPushButton("Calibrate from Ruler")
        self.calibrate_scale_button.clicked.connect(self.open_ruler_calibration)

        for widget in (
            self.optical_path_spin,
            self.camera_distance_spin,
            self.focal_length_spin,
            self.pixel_size_spin,
            self.static_tilt_spin,
            self.manual_scale_spin,
        ):
            widget.valueChanged.connect(self._refresh_scale_hint)
        self.scale_mode_combo.currentIndexChanged.connect(self._refresh_scale_hint)

        layout.addRow("Optical path (m)", self.optical_path_spin)
        layout.addRow("Camera-to-screen (m)", self.camera_distance_spin)
        layout.addRow("Lens focal length (mm)", self.focal_length_spin)
        layout.addRow("Pixel size (um)", self.pixel_size_spin)
        layout.addRow("Static tilt (mrad)", self.static_tilt_spin)
        layout.addRow("Scale mode", self.scale_mode_combo)
        layout.addRow("Manual scale (mm/px)", self.manual_scale_spin)
        layout.addRow("Ruler calibration", self.calibrate_scale_button)
        layout.addRow("Scale estimate", self.scale_hint_label)
        return group

    def _build_analysis_group(self) -> QGroupBox:
        group = QGroupBox("Analysis")
        layout = QGridLayout(group)

        self.axis_combo = QComboBox()
        self.axis_combo.addItems(["Y", "X", "Radial"])
        self.roi_x_spin = self._make_int_spin(0, 4096, 0)
        self.roi_y_spin = self._make_int_spin(0, 4096, 0)
        self.roi_width_spin = self._make_int_spin(16, 4096, 1440)
        self.roi_height_spin = self._make_int_spin(16, 4096, 1080)
        self.threshold_spin = self._make_float_spin(0.0, 95.0, 10.0, decimals=1)
        self.analysis_stride_spin = self._make_int_spin(1, 100, 1)
        self.background_average_spin = self._make_int_spin(1, 512, 16)
        self.profile_overlay_check = QCheckBox("Overlay X/Y profiles on preview")
        self.profile_overlay_check.setChecked(True)
        self.profile_refresh_spin = self._make_float_spin(0.2, 10.0, 2.0, decimals=1)
        self.profile_points_spin = self._make_int_spin(64, 2048, 256)
        self.contrast_mode_combo = QComboBox()
        self.contrast_mode_combo.addItems(["Auto", "Fixed"])
        self.contrast_interval_spin = self._make_int_spin(1, 200, 10)
        self.subtract_background_check = QCheckBox("Subtract captured background")
        self.gaussian_refinement_check = QCheckBox("Enable 2D Gaussian refinement")
        self.gaussian_refinement_check.setChecked(True)

        self.auto_roi_button = QPushButton("Auto ROI from Brightest Spot")
        self.apply_analysis_button = QPushButton("Apply Analysis Settings")
        self.roi_hint_label = QLabel("Tip: drag directly in the preview image to define the ROI.")
        self.roi_hint_label.setWordWrap(True)

        self.auto_roi_button.clicked.connect(self.auto_center_roi)
        self.apply_analysis_button.clicked.connect(self.apply_analysis_settings_live)

        self.profile_overlay_check.stateChanged.connect(self.apply_display_preferences)
        self.profile_refresh_spin.valueChanged.connect(self.apply_display_preferences)
        self.profile_points_spin.valueChanged.connect(self.apply_display_preferences)
        self.contrast_mode_combo.currentIndexChanged.connect(self.apply_display_preferences)
        self.contrast_interval_spin.valueChanged.connect(self.apply_display_preferences)

        layout.addWidget(QLabel("Primary axis"), 0, 0)
        layout.addWidget(self.axis_combo, 0, 1)
        layout.addWidget(QLabel("ROI X"), 1, 0)
        layout.addWidget(self.roi_x_spin, 1, 1)
        layout.addWidget(QLabel("ROI Y"), 2, 0)
        layout.addWidget(self.roi_y_spin, 2, 1)
        layout.addWidget(QLabel("ROI width"), 3, 0)
        layout.addWidget(self.roi_width_spin, 3, 1)
        layout.addWidget(QLabel("ROI height"), 4, 0)
        layout.addWidget(self.roi_height_spin, 4, 1)
        layout.addWidget(QLabel("Threshold (% of peak)"), 5, 0)
        layout.addWidget(self.threshold_spin, 5, 1)
        layout.addWidget(QLabel("Analysis stride"), 6, 0)
        layout.addWidget(self.analysis_stride_spin, 6, 1)
        layout.addWidget(QLabel("Background averaging"), 7, 0)
        layout.addWidget(self.background_average_spin, 7, 1)
        layout.addWidget(self.profile_overlay_check, 8, 0, 1, 2)
        layout.addWidget(QLabel("Profile refresh (Hz)"), 9, 0)
        layout.addWidget(self.profile_refresh_spin, 9, 1)
        layout.addWidget(QLabel("Profile max points"), 10, 0)
        layout.addWidget(self.profile_points_spin, 10, 1)
        layout.addWidget(QLabel("Contrast mode"), 11, 0)
        layout.addWidget(self.contrast_mode_combo, 11, 1)
        layout.addWidget(QLabel("Contrast every N frames"), 12, 0)
        layout.addWidget(self.contrast_interval_spin, 12, 1)
        layout.addWidget(self.subtract_background_check, 13, 0, 1, 2)
        layout.addWidget(self.gaussian_refinement_check, 14, 0, 1, 2)
        layout.addWidget(self.auto_roi_button, 15, 0, 1, 2)
        layout.addWidget(self.apply_analysis_button, 16, 0, 1, 2)
        layout.addWidget(self.roi_hint_label, 17, 0, 1, 2)
        return group

    def _build_recording_group(self) -> QGroupBox:
        group = QGroupBox("Recording")
        layout = QGridLayout(group)

        self.sample_interval_spin = self._make_float_spin(0.001, 3600.0, 0.100, decimals=3)
        self.stop_mode_combo = QComboBox()
        self.stop_mode_combo.addItems(["Manual Stop", "N Points", "Duration"])
        self.target_points_spin = self._make_int_spin(1, 100_000_000, 1200)
        self.duration_value_spin = self._make_float_spin(0.001, 100_000.0, 120.0, decimals=3)
        self.duration_unit_combo = QComboBox()
        self.duration_unit_combo.addItems(["s", "min", "h"])
        self.output_csv_edit = QLineEdit(os.path.abspath(DEFAULT_OUTPUT_CSV_NAME))
        self.browse_output_csv_button = QPushButton("Browse...")
        self.recording_hint_label = QLabel()
        self.recording_hint_label.setWordWrap(True)

        self.browse_output_csv_button.clicked.connect(self.browse_output_csv_path)
        self.sample_interval_spin.valueChanged.connect(self._refresh_recording_controls)
        self.stop_mode_combo.currentIndexChanged.connect(self._refresh_recording_controls)
        self.target_points_spin.valueChanged.connect(self._refresh_recording_controls)
        self.duration_value_spin.valueChanged.connect(self._refresh_recording_controls)
        self.duration_unit_combo.currentIndexChanged.connect(self._refresh_recording_controls)
        self.output_csv_edit.textChanged.connect(self._refresh_recording_plan_hint)
        self.frame_rate_spin.valueChanged.connect(self._refresh_recording_plan_hint)

        output_row = QHBoxLayout()
        output_row.setContentsMargins(0, 0, 0, 0)
        output_row.addWidget(self.output_csv_edit, stretch=1)
        output_row.addWidget(self.browse_output_csv_button)

        duration_row = QHBoxLayout()
        duration_row.setContentsMargins(0, 0, 0, 0)
        duration_row.addWidget(self.duration_value_spin, stretch=1)
        duration_row.addWidget(self.duration_unit_combo)

        layout.addWidget(QLabel("Sample interval (s)"), 0, 0)
        layout.addWidget(self.sample_interval_spin, 0, 1)
        layout.addWidget(QLabel("Stop condition"), 1, 0)
        layout.addWidget(self.stop_mode_combo, 1, 1)
        layout.addWidget(QLabel("Target points"), 2, 0)
        layout.addWidget(self.target_points_spin, 2, 1)
        layout.addWidget(QLabel("Target duration"), 3, 0)
        layout.addLayout(duration_row, 3, 1)
        layout.addWidget(QLabel("Output CSV"), 4, 0)
        layout.addLayout(output_row, 4, 1)
        layout.addWidget(self.recording_hint_label, 5, 0, 1, 2)

        self._refresh_recording_controls()
        return group

    def _build_session_group(self) -> QGroupBox:
        group = QGroupBox("Session")
        layout = QGridLayout(group)

        self.reset_reference_button = QPushButton("Reset Reference")
        self.capture_background_button = QPushButton("Capture Background")
        self.clear_background_button = QPushButton("Clear Background")
        self.clear_data_button = QPushButton("Clear Data")
        self.export_button = QPushButton("Export Session")
        self.snapshot_button = QPushButton("Save Snapshot")

        self.reset_reference_button.clicked.connect(self.reset_reference)
        self.capture_background_button.clicked.connect(self.capture_background)
        self.clear_background_button.clicked.connect(self.clear_background)
        self.clear_data_button.clicked.connect(self.clear_data)
        self.export_button.clicked.connect(self.export_session)
        self.snapshot_button.clicked.connect(self.save_snapshot)

        layout.addWidget(self.reset_reference_button, 0, 0)
        layout.addWidget(self.capture_background_button, 0, 1)
        layout.addWidget(self.clear_background_button, 1, 0)
        layout.addWidget(self.clear_data_button, 1, 1)
        layout.addWidget(self.export_button, 2, 0)
        layout.addWidget(self.snapshot_button, 2, 1)
        return group

    def _build_metrics_group(self) -> QGroupBox:
        group = QGroupBox("Live Metrics")
        layout = QFormLayout(group)

        self.metric_status_label = QLabel("Idle")
        self.metric_scale_label = QLabel("-")
        self.metric_samples_label = QLabel("0")
        self.metric_fps_label = QLabel("-")
        self.metric_center_label = QLabel("-")
        self.metric_tilt_label = QLabel("-")
        self.metric_absolute_tilt_label = QLabel("-")
        self.metric_fwhm_label = QLabel("-")
        self.metric_fit_label = QLabel("-")

        for widget in (
            self.metric_status_label,
            self.metric_scale_label,
            self.metric_samples_label,
            self.metric_fps_label,
            self.metric_center_label,
            self.metric_tilt_label,
            self.metric_absolute_tilt_label,
            self.metric_fwhm_label,
            self.metric_fit_label,
        ):
            widget.setWordWrap(True)

        layout.addRow("Status", self.metric_status_label)
        layout.addRow("Scale", self.metric_scale_label)
        layout.addRow("Samples", self.metric_samples_label)
        layout.addRow("Acquisition FPS", self.metric_fps_label)
        layout.addRow("Centroid (px)", self.metric_center_label)
        layout.addRow("Tilt jitter (urad)", self.metric_tilt_label)
        layout.addRow("Absolute tilt (mrad)", self.metric_absolute_tilt_label)
        layout.addRow("FWHM major/minor (px)", self.metric_fwhm_label)
        layout.addRow("Fit diagnostics", self.metric_fit_label)
        return group

    @staticmethod
    def _make_float_spin(
        minimum: float,
        maximum: float,
        value: float,
        *,
        decimals: int = 3,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setDecimals(decimals)
        spin.setSingleStep(10 ** (-min(decimals, 2)))
        return spin

    @staticmethod
    def _make_int_spin(minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    def _sync_control_states(self) -> None:
        preview_running = self.preview_running
        analysis_running = self.analysis_running
        self.connect_preview_button.setEnabled(not preview_running)
        self.disconnect_button.setEnabled(preview_running)
        self.start_analysis_button.setEnabled(preview_running and not analysis_running)
        self.stop_analysis_button.setEnabled(preview_running and analysis_running)
        self.apply_camera_button.setEnabled(True)
        self.clear_data_button.setEnabled(not analysis_running)
        self.export_button.setEnabled(self.record_count > 0 and not analysis_running)
        self._refresh_recording_controls()

    def _set_analysis_metrics_placeholder(self, text: str) -> None:
        self.metric_center_label.setText(text)
        self.metric_tilt_label.setText(text)
        self.metric_absolute_tilt_label.setText(text)
        self.metric_fwhm_label.setText(text)
        self.metric_fit_label.setText(text)

    def current_camera_settings(self) -> CameraSettings:
        return CameraSettings(
            exposure_us=self.exposure_spin.value(),
            gain_db=self.gain_spin.value(),
            frame_rate_fps=self.frame_rate_spin.value(),
            pixel_format=self.pixel_format_combo.currentText(),
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            offset_x=self.offset_x_spin.value(),
            offset_y=self.offset_y_spin.value(),
            serial_number=self.serial_edit.text().strip(),
        )

    def current_geometry_settings(self) -> GeometrySettings:
        return GeometrySettings(
            optical_path_m=self.optical_path_spin.value(),
            camera_to_screen_m=self.camera_distance_spin.value(),
            lens_focal_length_mm=self.focal_length_spin.value(),
            pixel_size_um=self.pixel_size_spin.value(),
            static_tilt_mrad=self.static_tilt_spin.value(),
            analysis_axis=self.axis_combo.currentText(),
            use_manual_scale=self.scale_mode_combo.currentIndex() == 1,
            manual_scale_mm_per_px=self.manual_scale_spin.value(),
        )

    def current_analysis_settings(self) -> AnalysisSettings:
        return AnalysisSettings(
            roi_x=self.roi_x_spin.value(),
            roi_y=self.roi_y_spin.value(),
            roi_width=self.roi_width_spin.value(),
            roi_height=self.roi_height_spin.value(),
            threshold_fraction=self.threshold_spin.value() / 100.0,
            subtract_background=self.subtract_background_check.isChecked(),
            gaussian_refinement=self.gaussian_refinement_check.isChecked(),
            analysis_stride=self.analysis_stride_spin.value(),
            sample_interval_s=self.sample_interval_spin.value(),
            background_average_count=self.background_average_spin.value(),
        )

    def _refresh_scale_hint(self) -> None:
        try:
            geometry = self.current_geometry_settings()
            scale = scale_mm_per_px(geometry)
            angle_per_pixel_urad = scale / (geometry.optical_path_m * 1000.0) * 1.0e6
            text = (
                f"{scale:.6f} mm/px at screen plane | "
                f"{angle_per_pixel_urad:.3f} urad/px over {geometry.optical_path_m:.3f} m"
            )
        except Exception as exc:
            text = f"Invalid geometry: {exc}"
        self.scale_hint_label.setText(text)
        self.metric_scale_label.setText(text)

    def validate_settings(self) -> bool:
        try:
            _ = scale_mm_per_px(self.current_geometry_settings())
        except Exception as exc:
            QMessageBox.warning(self, "Invalid Geometry", str(exc))
            return False
        return True

    def start_preview(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(
                self,
                "Preview Running",
                "A preview session is already running. Disconnect first if you want to reconnect.",
            )
            return
        if not self.validate_settings():
            return

        self.last_display_packet = None
        self.last_result = None
        self.preview_running = True
        self.analysis_running = False
        self._set_analysis_metrics_placeholder("Waiting for analysis")
        self._sync_control_states()

        self.worker = AcquisitionWorker(
            self.backend_combo.currentText(),
            self.current_camera_settings(),
            self.current_geometry_settings(),
            self.current_analysis_settings(),
        )
        self.worker.frame_available.connect(self.on_frame_available)
        self.worker.analysis_result.connect(self.on_analysis_result)
        self.worker.status_message.connect(self.on_status_message)
        self.worker.error_message.connect(self.on_error_message)
        self.worker.connected_message.connect(self.on_connected_message)
        self.worker.applied_camera_settings.connect(self.on_applied_camera_settings)
        self.worker.analysis_state_changed.connect(self.on_analysis_state_changed)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

        self.metric_status_label.setText("Starting preview")
        self.statusBar().showMessage("Starting camera preview...")

    def disconnect_camera(self) -> None:
        if self.worker is None:
            return
        self.worker.stop()
        self.worker.wait(3000)

    def start_analysis(self) -> None:
        if self.worker is None or not self.worker.isRunning():
            QMessageBox.information(
                self,
                "Preview Required",
                "Connect the camera preview first so you can confirm the image and ROI before analysis.",
            )
            return
        if self.analysis_running:
            QMessageBox.information(self, "Analysis Running", "Analysis is already running.")
            return
        if not self.validate_settings():
            return

        plan = self._validate_recording_plan()
        if plan is None:
            return

        self.clear_data()
        try:
            self._open_session_csv(plan.output_csv_path)
        except OSError as exc:
            QMessageBox.critical(self, "Cannot Open Output CSV", str(exc))
            self._close_session_csv(clear_path=True)
            return

        self._activate_recording_plan(plan)
        self.worker.update_camera_settings(self.current_camera_settings())
        self.worker.update_geometry_settings(self.current_geometry_settings())
        self.worker.update_analysis_settings(self.current_analysis_settings())
        self.worker.start_analysis()
        self.statusBar().showMessage(f"Analysis start requested. Recording to {plan.output_csv_path}")

    def stop_analysis(self) -> None:
        if self.worker is None or not self.worker.isRunning():
            return
        self._flush_session_csv()
        self.worker.stop_analysis()

    def apply_live_settings(self) -> None:
        if not self.validate_settings():
            return
        self._refresh_scale_hint()
        if self.worker is None or not self.worker.isRunning():
            self.statusBar().showMessage(
                "Settings updated locally. Click Connect Preview to apply them to the camera."
            )
            return
        self.worker.update_camera_settings(self.current_camera_settings())
        self.worker.update_geometry_settings(self.current_geometry_settings())
        self.worker.update_analysis_settings(self.current_analysis_settings())
        self.statusBar().showMessage("Live settings update requested.")

    def apply_analysis_settings_live(self) -> None:
        if not self.validate_settings():
            return
        self._refresh_scale_hint()
        if self.worker is None or not self.worker.isRunning():
            self.statusBar().showMessage(
                "Analysis settings updated locally. Click Connect Preview to apply them to live acquisition."
            )
            return
        self.worker.update_geometry_settings(self.current_geometry_settings())
        self.worker.update_analysis_settings(self.current_analysis_settings())
        self.statusBar().showMessage("Analysis settings update requested.")

    def apply_display_preferences(self, *_args) -> None:
        if hasattr(self, "contrast_interval_spin"):
            auto_mode = self.contrast_mode_combo.currentText() == "Auto"
            self.contrast_interval_spin.setEnabled(auto_mode)
        self.live_canvas.configure_display(
            show_profiles=self.profile_overlay_check.isChecked(),
            profile_refresh_hz=self.profile_refresh_spin.value(),
            profile_max_points=self.profile_points_spin.value(),
            contrast_mode=self.contrast_mode_combo.currentText(),
            contrast_refresh_frames=self.contrast_interval_spin.value(),
        )
        if self.last_display_packet is not None:
            self._render_frame_packet(self.last_display_packet)

    def _stop_mode_uses_points(self) -> bool:
        return self.stop_mode_combo.currentText() == "N Points"

    def _stop_mode_uses_duration(self) -> bool:
        return self.stop_mode_combo.currentText() == "Duration"

    def _duration_unit_scale(self) -> float:
        unit = self.duration_unit_combo.currentText()
        if unit == "min":
            return 60.0
        if unit == "h":
            return 3600.0
        return 1.0

    def _current_target_duration_s(self) -> float:
        return self.duration_value_spin.value() * self._duration_unit_scale()

    def _normalized_output_csv_path(self) -> str:
        raw_path = self.output_csv_edit.text().strip()
        if not raw_path:
            return ""
        normalized = os.path.abspath(os.path.expanduser(raw_path))
        if not normalized.lower().endswith(".csv"):
            normalized += ".csv"
        return normalized

    def browse_output_csv_path(self) -> None:
        default_path = self._normalized_output_csv_path() or os.path.abspath(DEFAULT_OUTPUT_CSV_NAME)
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Select Output CSV",
            default_path,
            "CSV Files (*.csv)",
        )
        if not filename:
            return
        if not filename.lower().endswith(".csv"):
            filename += ".csv"
        self.output_csv_edit.setText(filename)

    def _refresh_recording_controls(self, *_args) -> None:
        uses_points = self._stop_mode_uses_points()
        uses_duration = self._stop_mode_uses_duration()
        controls_enabled = not self.analysis_running
        self.sample_interval_spin.setEnabled(controls_enabled)
        self.stop_mode_combo.setEnabled(controls_enabled)
        self.target_points_spin.setEnabled(controls_enabled and uses_points)
        self.duration_value_spin.setEnabled(controls_enabled and uses_duration)
        self.duration_unit_combo.setEnabled(controls_enabled and uses_duration)
        self.output_csv_edit.setEnabled(controls_enabled)
        self.browse_output_csv_button.setEnabled(controls_enabled)
        self._refresh_recording_plan_hint()

    def _refresh_recording_plan_hint(self, *_args) -> None:
        interval_s = self.sample_interval_spin.value()
        stride = max(int(self.analysis_stride_spin.value()), 1)
        configured_fps = max(self.frame_rate_spin.value(), 1.0e-9)

        live_fps = 0.0
        if self.last_display_packet is not None and self.last_display_packet.acquisition_fps > 0.0:
            live_fps = float(self.last_display_packet.acquisition_fps)
        effective_fps = live_fps if live_fps > 0.0 else configured_fps
        frame_period_s = 1.0 / max(effective_fps, 1.0e-9)
        min_interval_s = stride * frame_period_s
        interval_ok = interval_s + 1.0e-9 >= min_interval_s

        if live_fps > 0.0:
            fps_text = f"Live FPS {live_fps:.2f} (configured {configured_fps:.2f})"
        else:
            fps_text = f"Configured FPS {configured_fps:.2f}"

        plan_text = "Manual stop"
        if self.analysis_running:
            if self._active_stop_mode == "N Points" and self._active_target_points is not None:
                plan_text = f"Running: {self.record_count} / {self._active_target_points} points"
            elif self._active_stop_mode == "Duration" and self._active_target_duration_s is not None:
                elapsed_s = 0.0
                if self._session_zero_time_s is not None and self.last_result is not None:
                    elapsed_s = max(self.last_result.timestamp_s - self._session_zero_time_s, 0.0)
                plan_text = (
                    f"Running: {elapsed_s:.1f} / {self._active_target_duration_s:.1f} s"
                )
            else:
                plan_text = "Running: manual stop"
        else:
            if self._stop_mode_uses_points():
                target_points = self.target_points_spin.value()
                estimated_duration_s = target_points * interval_s
                plan_text = f"Stop after {target_points} points (~{estimated_duration_s:.1f} s)"
            elif self._stop_mode_uses_duration():
                duration_s = self._current_target_duration_s()
                estimated_points = max(int(duration_s / max(interval_s, 1.0e-9)), 1)
                plan_text = f"Stop after {duration_s:.1f} s (~{estimated_points} points)"

        status_text = "OK" if interval_ok else "Too fast for the available frame rate"
        output_path = self._normalized_output_csv_path() or "<not set>"
        self.recording_hint_label.setText(
            " | ".join(
                [
                    f"{fps_text} -> frame period {frame_period_s * 1000.0:.1f} ms",
                    f"Stride {stride} -> min interval {min_interval_s * 1000.0:.1f} ms",
                    f"Requested interval {interval_s * 1000.0:.1f} ms ({status_text})",
                    plan_text,
                    output_path,
                ]
            )
        )

    def _validate_recording_plan(self) -> RecordingPlan | None:
        output_csv_path = self._normalized_output_csv_path()
        if not output_csv_path:
            QMessageBox.warning(self, "Output CSV Required", "Set the CSV file path before starting analysis.")
            return None
        if os.path.isdir(output_csv_path):
            QMessageBox.warning(self, "Invalid Output Path", "The output CSV path points to a directory.")
            return None

        interval_s = self.sample_interval_spin.value()
        stride = max(int(self.analysis_stride_spin.value()), 1)
        configured_fps = max(self.frame_rate_spin.value(), 1.0e-9)
        live_fps = 0.0
        if self.last_display_packet is not None and self.last_display_packet.acquisition_fps > 0.0:
            live_fps = float(self.last_display_packet.acquisition_fps)
        effective_fps = live_fps if live_fps > 0.0 else configured_fps
        min_interval_s = stride / max(effective_fps, 1.0e-9)
        fps_source = "live preview FPS" if live_fps > 0.0 else "configured camera FPS"
        if interval_s + 1.0e-9 < min_interval_s:
            QMessageBox.warning(
                self,
                "Sampling Interval Too Short",
                (
                    f"Requested sample interval {interval_s:.6f} s is shorter than the minimum achievable "
                    f"interval {min_interval_s:.6f} s implied by {fps_source} ({effective_fps:.2f} fps) "
                    f"and analysis stride {stride}. Increase the interval or raise the camera frame rate."
                ),
            )
            return None

        if os.path.exists(output_csv_path):
            response = QMessageBox.question(
                self,
                "Overwrite Existing CSV?",
                f"{output_csv_path} already exists. Overwrite it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if response != QMessageBox.Yes:
                return None

        stop_mode = self.stop_mode_combo.currentText()
        target_points = None
        target_duration_s = None
        if stop_mode == "N Points":
            target_points = int(self.target_points_spin.value())
        elif stop_mode == "Duration":
            target_duration_s = float(self._current_target_duration_s())

        return RecordingPlan(
            sample_interval_s=float(interval_s),
            stop_mode=stop_mode,
            target_points=target_points,
            target_duration_s=target_duration_s,
            output_csv_path=output_csv_path,
        )

    def _open_session_csv(self, output_csv_path: str) -> None:
        directory = os.path.dirname(output_csv_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        handle = open(output_csv_path, "w", newline="", encoding="utf-8", buffering=1)
        fieldnames = list(FrameAnalysisResult.__dataclass_fields__.keys()) + ["relative_time_s"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        handle.flush()
        self._session_csv_handle = handle
        self._session_csv_writer = writer
        self._session_csv_temp_path = output_csv_path
        self._session_zero_time_s = None
        self._session_csv_pending_rows = 0

    def _activate_recording_plan(self, plan: RecordingPlan) -> None:
        self._active_stop_mode = plan.stop_mode
        self._active_target_points = plan.target_points
        self._active_target_duration_s = plan.target_duration_s
        self._refresh_recording_plan_hint()

    def _finalize_recording_if_complete(self, result: FrameAnalysisResult) -> None:
        if self.worker is None or not self.analysis_running:
            return
        if self._active_stop_mode == "N Points" and self._active_target_points is not None:
            if self.record_count >= self._active_target_points:
                self.statusBar().showMessage("Target point count reached. Stopping analysis.")
                self.worker.stop_analysis()
                return
        if self._active_stop_mode == "Duration" and self._active_target_duration_s is not None:
            if self._session_zero_time_s is None:
                return
            elapsed_s = result.timestamp_s - self._session_zero_time_s
            if elapsed_s + 1.0e-9 >= self._active_target_duration_s:
                self.statusBar().showMessage("Target duration reached. Stopping analysis.")
                self.worker.stop_analysis()

    def reset_reference(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_reference_reset()
        self.statusBar().showMessage("Reference reset requested.")

    def capture_background(self) -> None:
        if self.worker is None or not self.worker.isRunning():
            QMessageBox.information(self, "No Preview", "Start the preview before capturing a background.")
            return
        self.worker.request_background_capture(self.background_average_spin.value())

    def clear_background(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.clear_background()
        self.statusBar().showMessage("Background cleared.")

    def _flush_session_csv(self) -> None:
        if self._session_csv_handle is not None:
            self._session_csv_handle.flush()
        self._session_csv_pending_rows = 0

    def _close_session_csv(self, *, clear_path: bool) -> None:
        if self._session_csv_handle is not None:
            self._session_csv_handle.flush()
            self._session_csv_handle.close()
        self._session_csv_handle = None
        self._session_csv_writer = None
        self._session_csv_pending_rows = 0
        if clear_path:
            self._session_csv_temp_path = None

    def _append_result_to_session_csv(self, result: FrameAnalysisResult) -> None:
        if self._session_csv_writer is None or self._session_csv_handle is None:
            return
        if self._session_zero_time_s is None:
            self._session_zero_time_s = result.timestamp_s
        row = result.to_dict()
        row["relative_time_s"] = result.timestamp_s - self._session_zero_time_s
        self._session_csv_writer.writerow(row)
        self._session_csv_pending_rows += 1
        if self._session_csv_pending_rows >= SESSION_CSV_FLUSH_INTERVAL:
            self._flush_session_csv()

    def _trim_plot_records(self, current_time_s: float) -> None:
        while self.records and current_time_s - self.records[0].timestamp_s > TIME_SERIES_WINDOW_S:
            self.records.popleft()

    def clear_data(self) -> None:
        self._close_session_csv(clear_path=True)
        self.records = deque()
        self.record_count = 0
        self.session_summary = OnlineSessionSummary()
        self._session_zero_time_s = None
        self.last_result = None
        self.last_plot_refresh_s = 0.0
        self._active_stop_mode = "Manual Stop"
        self._active_target_points = None
        self._active_target_duration_s = None
        self.metric_samples_label.setText("0")
        self.time_series_canvas.update_view([])
        self._update_summary_text()
        self._refresh_recording_plan_hint()
        self._sync_control_states()
        if not self.analysis_running:
            self._set_analysis_metrics_placeholder("Preview only")
        self.statusBar().showMessage("Recorded metrics cleared.")

    def auto_center_roi(self) -> None:
        if self.last_display_packet is None:
            QMessageBox.information(
                self,
                "No Frame Available",
                "Acquire at least one preview frame before using Auto ROI.",
            )
            return

        full_frame = self.last_display_packet.full_frame.astype(np.float64, copy=False)
        smoothed = gaussian_filter(full_frame, sigma=2.0)
        peak_index = int(np.argmax(smoothed))
        peak_y, peak_x = np.unravel_index(peak_index, smoothed.shape)

        roi_width = self.roi_width_spin.value()
        roi_height = self.roi_height_spin.value()
        x0 = max(0, min(full_frame.shape[1] - roi_width, peak_x - roi_width // 2))
        y0 = max(0, min(full_frame.shape[0] - roi_height, peak_y - roi_height // 2))
        self.roi_x_spin.setValue(int(x0))
        self.roi_y_spin.setValue(int(y0))
        self.apply_analysis_settings_live()
        self.statusBar().showMessage("ROI centered on the brightest region.")

    def on_canvas_roi_selected(self, roi_x: int, roi_y: int, roi_width: int, roi_height: int) -> None:
        if self.last_display_packet is None:
            return

        frame_height, frame_width = self.last_display_packet.full_frame.shape
        roi_width = min(max(int(roi_width), self.roi_width_spin.minimum()), frame_width)
        roi_height = min(max(int(roi_height), self.roi_height_spin.minimum()), frame_height)
        roi_x = max(0, min(frame_width - roi_width, int(roi_x)))
        roi_y = max(0, min(frame_height - roi_height, int(roi_y)))

        self._set_spin_value(self.roi_x_spin, roi_x)
        self._set_spin_value(self.roi_y_spin, roi_y)
        self._set_spin_value(self.roi_width_spin, roi_width)
        self._set_spin_value(self.roi_height_spin, roi_height)
        self.apply_analysis_settings_live()
        self.statusBar().showMessage(
            f"ROI selected from preview: x={roi_x}, y={roi_y}, width={roi_width}, height={roi_height}"
        )

    def open_ruler_calibration(self) -> None:
        if self.last_display_packet is None:
            QMessageBox.information(
                self,
                "No Frame Available",
                "Acquire a preview frame before calibrating from a ruler.",
            )
            return

        dialog = RulerCalibrationDialog(self.last_display_packet.full_frame, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        scale_mm_per_px = dialog.selected_scale_mm_per_px()
        if scale_mm_per_px is None:
            return

        self.scale_mode_combo.setCurrentIndex(1)
        self.manual_scale_spin.setValue(scale_mm_per_px)
        self._refresh_scale_hint()
        self.apply_analysis_settings_live()
        self.statusBar().showMessage(
            f"Manual ruler calibration applied: {scale_mm_per_px:.6f} mm/px"
        )

    def save_snapshot(self) -> None:
        if self.last_display_packet is None:
            QMessageBox.information(self, "No Frame Available", "Acquire a preview frame before saving a snapshot.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Snapshot",
            "beam_preview_snapshot.png",
            "PNG Image (*.png)",
        )
        if not filename:
            return
        self.live_canvas.figure.savefig(filename, dpi=160)
        self.statusBar().showMessage(f"Snapshot saved to {filename}")

    def export_session(self) -> None:
        if self.analysis_running:
            QMessageBox.information(self, "Analysis Running", "Stop analysis before exporting the summary files.")
            return
        if self.record_count == 0 or self._session_csv_temp_path is None:
            QMessageBox.information(self, "No Data", "There are no analysis records to export.")
            return

        csv_path = self._session_csv_temp_path
        prefix, _ = os.path.splitext(csv_path)
        json_path = f"{prefix}_summary.json"
        time_plot_path = f"{prefix}_timeseries.png"
        live_plot_path = f"{prefix}_preview.png"

        self._flush_session_csv()

        summary = self.session_summary.to_summary(
            self.axis_combo.currentText(),
            self.static_tilt_spin.value(),
        )
        payload = {
            "exported_at": datetime.now().isoformat(),
            "backend": self.backend_combo.currentText(),
            "camera_settings": asdict(self.current_camera_settings()),
            "geometry_settings": asdict(self.current_geometry_settings()),
            "analysis_settings": asdict(self.current_analysis_settings()),
            "session_summary": summary,
            "csv_path": csv_path,
        }
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

        self.time_series_canvas.figure.savefig(time_plot_path, dpi=160)
        self.live_canvas.figure.savefig(live_plot_path, dpi=160)

        self.statusBar().showMessage(
            f"Summary exported next to CSV: {os.path.basename(json_path)}"
        )

    def _render_frame_packet(self, packet: FrameDisplayPacket) -> None:
        self.last_display_packet = packet
        self.live_canvas.update_view(
            packet.full_frame,
            packet.roi_tuple,
            packet.result,
            packet.analysis_enabled,
            self.subtract_background_check.isChecked(),
            packet.timestamp_s,
        )
        self.metric_fps_label.setText(f"{packet.acquisition_fps:.2f}")
        self._refresh_recording_plan_hint()
        if not packet.analysis_enabled and not self.analysis_running:
            self._set_analysis_metrics_placeholder("Preview only")

    def on_frame_available(self) -> None:
        if self.worker is None:
            return
        packet = self.worker.take_latest_display_packet()
        if packet is None:
            return
        self._render_frame_packet(packet)

    def on_frame_packet(self, packet: FrameDisplayPacket) -> None:
        self._render_frame_packet(packet)

    def on_analysis_result(self, result: FrameAnalysisResult) -> None:
        self.last_result = result
        self.record_count += 1
        self.session_summary.update(result)
        self._append_result_to_session_csv(result)
        self.records.append(result)
        self._trim_plot_records(result.timestamp_s)
        self.metric_samples_label.setText(str(self.record_count))
        self.metric_center_label.setText(
            f"({result.center_x_px:.2f}, {result.center_y_px:.2f})"
        )
        self.metric_tilt_label.setText(
            f"X {result.tilt_x_urad:.3f} | "
            f"Y {result.tilt_y_urad:.3f} | "
            f"R {result.radial_tilt_urad:.3f}"
        )
        self.metric_absolute_tilt_label.setText(f"{result.absolute_tilt_mrad:.6f}")
        self.metric_fwhm_label.setText(
            f"{result.fwhm_major_px:.2f} / {result.fwhm_minor_px:.2f}"
        )
        if result.fit_success:
            self.metric_fit_label.setText(
                f"R^2 {result.fit_r_squared:.5f}, RMSE {result.fit_rmse:.3f}"
            )
        else:
            self.metric_fit_label.setText("Moment estimate only")

        refresh_interval_s = 0.25
        if not self.last_plot_refresh_s or (
            result.timestamp_s - self.last_plot_refresh_s >= refresh_interval_s
        ):
            self.time_series_canvas.update_view(
                list(self.records),
                window_s=TIME_SERIES_WINDOW_S,
                max_points=MAX_TIME_SERIES_POINTS,
            )
            self._update_summary_text()
            self.last_plot_refresh_s = result.timestamp_s

        self._refresh_recording_plan_hint()
        self._finalize_recording_if_complete(result)

    def on_status_message(self, message: str) -> None:
        self.metric_status_label.setText(message)
        self.statusBar().showMessage(message)

    def on_error_message(self, message: str) -> None:
        self.metric_status_label.setText("Error")
        self.statusBar().showMessage("Acquisition error.")
        QMessageBox.critical(self, "Beam Tilt Analyzer", message)

    def on_connected_message(self, message: str) -> None:
        self.preview_running = True
        self.metric_status_label.setText(message)
        self.statusBar().showMessage(f"Connected to {message}")
        self._sync_control_states()

    def on_applied_camera_settings(self, settings: CameraSettings) -> None:
        self._set_spin_value(self.exposure_spin, settings.exposure_us)
        self._set_spin_value(self.gain_spin, settings.gain_db)
        self._set_spin_value(self.frame_rate_spin, settings.frame_rate_fps)
        self._set_combo_value(self.pixel_format_combo, settings.pixel_format)
        self._set_spin_value(self.width_spin, settings.width)
        self._set_spin_value(self.height_spin, settings.height)
        self._set_spin_value(self.offset_x_spin, settings.offset_x)
        self._set_spin_value(self.offset_y_spin, settings.offset_y)
        self._refresh_recording_plan_hint()

    def on_analysis_state_changed(self, enabled: bool) -> None:
        self.analysis_running = enabled
        if not enabled:
            self._flush_session_csv()
            self._close_session_csv(clear_path=False)
            self._set_analysis_metrics_placeholder("Preview only")
        else:
            self.metric_status_label.setText("Analysis running")
        self._sync_control_states()
        self._refresh_recording_plan_hint()

    def on_worker_finished(self) -> None:
        self._flush_session_csv()
        self._close_session_csv(clear_path=False)
        self.preview_running = False
        self.analysis_running = False
        self.metric_status_label.setText("Disconnected")
        self._set_analysis_metrics_placeholder("Preview not started")
        self.statusBar().showMessage("Acquisition finished.")
        self.worker = None
        self._sync_control_states()
        self._refresh_recording_plan_hint()

    @staticmethod
    def _set_spin_value(spin_box, value: float | int) -> None:
        blocked = spin_box.blockSignals(True)
        spin_box.setValue(value)
        spin_box.blockSignals(blocked)

    @staticmethod
    def _set_combo_value(combo_box: QComboBox, value: str) -> None:
        blocked = combo_box.blockSignals(True)
        index = combo_box.findText(value)
        if index >= 0:
            combo_box.setCurrentIndex(index)
        combo_box.blockSignals(blocked)

    def _update_summary_text(self) -> None:
        summary = self.session_summary.to_summary(
            self.axis_combo.currentText(),
            self.static_tilt_spin.value(),
        )
        lines = [
            "Beam Tilt Session Summary",
            "",
            f"Selected axis: {summary['selected_axis']}",
            f"Samples: {summary['samples']}",
            f"Duration: {summary['duration_s']:.3f} s",
            f"Sampling rate: {summary['sampling_rate_hz']:.3f} Hz",
            f"Mean tilt: {summary['mean_tilt_urad']:.4f} urad",
            f"Std tilt: {summary['std_tilt_urad']:.4f} urad",
            f"RMS tilt: {summary['rms_tilt_urad']:.4f} urad",
            f"Peak-to-peak tilt: {summary['peak_to_peak_urad']:.4f} urad",
            f"Drift slope: {summary['drift_slope_urad_per_s']:.4f} urad/s",
            f"Mean absolute tilt: {summary['mean_absolute_tilt_mrad']:.6f} mrad",
            f"Mean FWHM major/minor: "
            f"{summary['mean_fwhm_major_px']:.3f} / {summary['mean_fwhm_minor_px']:.3f} px",
            "",
            "Workflow",
            "1. Click Connect Preview and confirm that the camera image is visible.",
            "2. Adjust exposure, gain, ROI, or offsets until the beam is framed correctly.",
            "3. If a ruler is visible on the screen, use Calibrate from Ruler to set mm/px.",
            "4. In Recording, set the sample interval, stop condition, and output CSV path.",
            "5. Click Start Analysis. Data are appended to the CSV during acquisition.",
            "6. Export the summary plots after enough data have been recorded.",
            "",
            "Methodology",
            "1. Background-correct the ROI if a dark frame has been captured.",
            "2. Estimate beam center and widths from thresholded intensity moments.",
            "3. Optionally refine the result with a rotated 2D Gaussian least-squares fit.",
            "4. Convert centroid displacement to angular jitter using dx / optical_path.",
        ]
        self.summary_text.setPlainText("\n".join(lines))

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming convention
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        self._close_session_csv(clear_path=False)
        super().closeEvent(event)


def main() -> int:
    """Entry point for the desktop application."""
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec_()
