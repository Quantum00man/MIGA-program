"""PyQt5 user interface for Basler beam-tilt measurements."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
import csv
import json
import os
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
    analyze_frame,
    clipped_roi,
    compute_session_summary,
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


class LiveImageCanvas(FigureCanvasQTAgg):
    """Matplotlib canvas for live camera preview and ROI overlays."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self.figure = Figure(figsize=(7.0, 5.0), constrained_layout=True)
        super().__init__(self.figure)
        self.setParent(parent)
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
        self.center_artist = self.ax.scatter([], [], marker="+", s=90, c="white")
        self.fwhm_ellipse = Ellipse(
            (0.0, 0.0),
            width=1.0,
            height=1.0,
            angle=0.0,
            fill=False,
            linewidth=1.4,
            edgecolor="white",
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
        )
        self.ax.add_patch(self.roi_rect)

    def update_view(
        self,
        frame_image: np.ndarray,
        roi_tuple: tuple[int, int, int, int],
        result: FrameAnalysisResult | None,
        analysis_enabled: bool,
        subtract_background: bool,
    ) -> None:
        display_image = frame_image.astype(np.float64, copy=False)
        frame_height, frame_width = display_image.shape
        self.image_artist.set_data(display_image)
        self.image_artist.set_extent((-0.5, frame_width - 0.5, -0.5, frame_height - 0.5))

        low = float(np.percentile(display_image, 2.0))
        high = float(np.percentile(display_image, 99.8))
        if not np.isfinite(low) or not np.isfinite(high) or low == high:
            low = float(np.min(display_image))
            high = float(np.max(display_image) + 1.0)
        self.image_artist.set_clim(low, high)

        roi_x, roi_y, roi_width, roi_height = roi_tuple
        self.roi_rect.set_xy((roi_x, roi_y))
        self.roi_rect.set_width(max(roi_width, 1.0))
        self.roi_rect.set_height(max(roi_height, 1.0))
        self.roi_rect.set_visible(True)

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
        if subtract_background and analysis_enabled:
            title += " | Background-subtracted analysis"
        self.ax.set_title(title)
        self.ax.set_xlim(0.0, max(display_image.shape[1] - 1, 1))
        self.ax.set_ylim(0.0, max(display_image.shape[0] - 1, 1))
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

    def update_view(self, records: list[FrameAnalysisResult], window_s: float = 60.0) -> None:
        if not records:
            for line in (self.line_x, self.line_y, self.line_r):
                line.set_data([], [])
            self.ax.relim()
            self.ax.autoscale_view()
            self.draw_idle()
            return

        time_axis = np.array([record.timestamp_s for record in records], dtype=np.float64)
        time_axis = time_axis - time_axis[0]
        if time_axis[-1] > window_s:
            keep = time_axis >= (time_axis[-1] - window_s)
            time_axis = time_axis[keep]
            records = [record for record, include in zip(records, keep) if include]

        x = np.array([record.tilt_x_urad for record in records], dtype=np.float64)
        y = np.array([record.tilt_y_urad for record in records], dtype=np.float64)
        radial = np.array([record.radial_tilt_urad for record in records], dtype=np.float64)

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

    frame_packet = pyqtSignal(object)
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

    def stop(self) -> None:
        self._stop_requested = True

    def start_analysis(self) -> None:
        self._analysis_enabled = True
        self._reset_reference_requested = True
        self._last_result = None
        self.analysis_state_changed.emit(True)
        self.status_message.emit(
            "Analysis started. The next valid fitted frame will define the reference center."
        )

    def stop_analysis(self) -> None:
        if not self._analysis_enabled:
            return
        self._analysis_enabled = False
        self._last_result = None
        self.analysis_state_changed.emit(False)
        self.status_message.emit("Analysis stopped. Live preview remains active.")

    def update_camera_settings(self, settings: CameraSettings) -> None:
        self._camera_settings = settings
        self._pending_camera_apply = True
        self._consecutive_timeouts = 0

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
                if self._analysis_enabled and packet.frame_index % stride == 0:
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
                    self.frame_packet.emit(display_packet)
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
        self.records: list[FrameAnalysisResult] = []
        self.last_display_packet: FrameDisplayPacket | None = None
        self.last_result: FrameAnalysisResult | None = None
        self.last_plot_refresh_s = 0.0
        self.preview_running = False
        self.analysis_running = False

        self.live_canvas = LiveImageCanvas()
        self.time_series_canvas = TimeSeriesCanvas()

        self._build_ui()
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
        self.subtract_background_check = QCheckBox("Subtract captured background")
        self.gaussian_refinement_check = QCheckBox("Enable 2D Gaussian refinement")
        self.gaussian_refinement_check.setChecked(True)

        self.auto_roi_button = QPushButton("Auto ROI from Brightest Spot")
        self.apply_analysis_button = QPushButton("Apply Analysis Settings")

        self.auto_roi_button.clicked.connect(self.auto_center_roi)
        self.apply_analysis_button.clicked.connect(self.apply_live_settings)

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
        layout.addWidget(self.subtract_background_check, 8, 0, 1, 2)
        layout.addWidget(self.gaussian_refinement_check, 9, 0, 1, 2)
        layout.addWidget(self.auto_roi_button, 10, 0, 1, 2)
        layout.addWidget(self.apply_analysis_button, 11, 0, 1, 2)
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
        self.worker.frame_packet.connect(self.on_frame_packet)
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

        self.clear_data()
        self.worker.update_camera_settings(self.current_camera_settings())
        self.worker.update_geometry_settings(self.current_geometry_settings())
        self.worker.update_analysis_settings(self.current_analysis_settings())
        self.worker.start_analysis()
        self.statusBar().showMessage("Analysis start requested.")

    def stop_analysis(self) -> None:
        if self.worker is None or not self.worker.isRunning():
            return
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

    def clear_data(self) -> None:
        self.records = []
        self.last_result = None
        self.last_plot_refresh_s = 0.0
        self.metric_samples_label.setText("0")
        self.time_series_canvas.update_view([])
        self._update_summary_text()
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
        self.apply_live_settings()
        self.statusBar().showMessage("ROI centered on the brightest region.")

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
        self.apply_live_settings()
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
        if not self.records:
            QMessageBox.information(self, "No Data", "There are no analysis records to export.")
            return
        directory = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if not directory:
            return

        timestamp_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = os.path.join(directory, f"beam_tilt_session_{timestamp_tag}")
        csv_path = f"{prefix}.csv"
        json_path = f"{prefix}_summary.json"
        time_plot_path = f"{prefix}_timeseries.png"
        live_plot_path = f"{prefix}_preview.png"

        relative_zero = self.records[0].timestamp_s
        rows: list[dict[str, Any]] = []
        for record in self.records:
            row = record.to_dict()
            row["relative_time_s"] = record.timestamp_s - relative_zero
            rows.append(row)

        with open(csv_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        summary = compute_session_summary(
            self.records,
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
        }
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

        self.time_series_canvas.figure.savefig(time_plot_path, dpi=160)
        self.live_canvas.figure.savefig(live_plot_path, dpi=160)

        self.statusBar().showMessage(
            f"Session exported: {os.path.basename(csv_path)}, {os.path.basename(json_path)}"
        )

    def on_frame_packet(self, packet: FrameDisplayPacket) -> None:
        self.last_display_packet = packet
        self.live_canvas.update_view(
            packet.full_frame,
            packet.roi_tuple,
            packet.result,
            packet.analysis_enabled,
            self.subtract_background_check.isChecked(),
        )
        self.metric_fps_label.setText(f"{packet.acquisition_fps:.2f}")
        if not packet.analysis_enabled and not self.analysis_running:
            self._set_analysis_metrics_placeholder("Preview only")

    def on_analysis_result(self, result: FrameAnalysisResult) -> None:
        self.last_result = result
        self.records.append(result)
        self.metric_samples_label.setText(str(len(self.records)))
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
            self.time_series_canvas.update_view(self.records)
            self._update_summary_text()
            self.last_plot_refresh_s = result.timestamp_s

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

    def on_analysis_state_changed(self, enabled: bool) -> None:
        self.analysis_running = enabled
        self._sync_control_states()
        if not enabled:
            self._set_analysis_metrics_placeholder("Preview only")
        else:
            self.metric_status_label.setText("Analysis running")

    def on_worker_finished(self) -> None:
        self.preview_running = False
        self.analysis_running = False
        self.metric_status_label.setText("Disconnected")
        self._set_analysis_metrics_placeholder("Preview not started")
        self.statusBar().showMessage("Acquisition finished.")
        self.worker = None
        self._sync_control_states()

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
        summary = compute_session_summary(
            self.records,
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
            "4. Click Start Analysis when the preview and ROI are ready.",
            "5. Export the session after enough data have been recorded.",
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
        super().closeEvent(event)


def main() -> int:
    """Entry point for the desktop application."""
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec_()
