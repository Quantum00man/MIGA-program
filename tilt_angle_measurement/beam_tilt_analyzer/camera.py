"""Camera backends for Basler acquisition and demo-mode testing."""

from __future__ import annotations

from dataclasses import dataclass
import math
import time

import numpy as np

try:
    from pypylon import genicam, pylon
except Exception:  # pragma: no cover - optional dependency
    genicam = None
    pylon = None


@dataclass
class CameraSettings:
    exposure_us: float = 5000.0
    gain_db: float = 0.0
    frame_rate_fps: float = 30.0
    pixel_format: str = "Mono8"
    width: int = 1440
    height: int = 1080
    offset_x: int = 0
    offset_y: int = 0
    serial_number: str = ""


@dataclass
class FramePacket:
    frame_index: int
    timestamp_s: float
    image: np.ndarray


class CameraBackendError(RuntimeError):
    """Raised when a camera backend cannot complete a requested operation."""


class CameraTimeoutError(CameraBackendError):
    """Raised when no frame arrives before the configured timeout."""


class BaseCameraBackend:
    """Abstract camera backend interface."""

    sensor_pixel_size_um: float = 3.45
    default_width: int = 1440
    default_height: int = 1080
    name: str = "Base"
    available_pixel_formats: tuple[str, ...] = ("Mono8", "Mono12")

    def connect(self, serial_number: str = "") -> str:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    def apply_settings(self, settings: CameraSettings) -> CameraSettings:
        raise NotImplementedError

    def start_grabbing(self) -> None:
        raise NotImplementedError

    def stop_grabbing(self) -> None:
        raise NotImplementedError

    def retrieve_frame(self, timeout_ms: int = 1000) -> FramePacket:
        raise NotImplementedError


class DemoCameraBackend(BaseCameraBackend):
    """Synthetic Gaussian beam source for UI and algorithm validation."""

    name = "Demo"

    def __init__(self) -> None:
        self._frame_index = 0
        self._settings = CameraSettings()
        self._rng = np.random.default_rng(20260710)
        self._last_frame_time = 0.0
        self._start_time = 0.0
        self._phase_walk_x = 0.0
        self._phase_walk_y = 0.0

    def connect(self, serial_number: str = "") -> str:
        self._frame_index = 0
        self._last_frame_time = 0.0
        self._start_time = time.perf_counter()
        return "Demo Gaussian source"

    def disconnect(self) -> None:
        return None

    def apply_settings(self, settings: CameraSettings) -> CameraSettings:
        self._settings = settings
        return self._settings

    def start_grabbing(self) -> None:
        self._frame_index = 0
        self._last_frame_time = time.perf_counter()
        self._start_time = self._last_frame_time

    def stop_grabbing(self) -> None:
        return None

    def retrieve_frame(self, timeout_ms: int = 1000) -> FramePacket:
        frame_period_s = 1.0 / max(self._settings.frame_rate_fps, 1.0)
        now = time.perf_counter()
        if self._last_frame_time > 0.0:
            target = self._last_frame_time + frame_period_s
            sleep_time = target - now
            if sleep_time > 0.0:
                time.sleep(min(sleep_time, timeout_ms / 1000.0))
        timestamp_s = time.perf_counter()
        self._last_frame_time = timestamp_s
        elapsed_s = timestamp_s - self._start_time

        width = max(16, int(self._settings.width))
        height = max(16, int(self._settings.height))
        y_idx, x_idx = np.indices((height, width), dtype=np.float64)

        self._phase_walk_x += 0.04 * self._rng.normal()
        self._phase_walk_y += 0.03 * self._rng.normal()
        center_x = width / 2.0 + 12.0 * math.sin(2.0 * math.pi * 0.9 * elapsed_s)
        center_x += 4.0 * math.sin(2.0 * math.pi * 8.0 * elapsed_s + self._phase_walk_x)
        center_x += self._rng.normal(scale=0.3)
        center_y = height / 2.0 + 9.0 * math.cos(2.0 * math.pi * 1.2 * elapsed_s)
        center_y += 5.0 * math.sin(2.0 * math.pi * 6.5 * elapsed_s + self._phase_walk_y)
        center_y += self._rng.normal(scale=0.3)

        sigma_x = 18.0 + 1.2 * math.sin(2.0 * math.pi * 0.3 * elapsed_s)
        sigma_y = 26.0 + 1.0 * math.cos(2.0 * math.pi * 0.35 * elapsed_s)
        theta = math.radians(12.0 * math.sin(2.0 * math.pi * 0.2 * elapsed_s))
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        x_shift = x_idx - center_x
        y_shift = y_idx - center_y
        x_rot = cos_t * x_shift + sin_t * y_shift
        y_rot = -sin_t * x_shift + cos_t * y_shift

        peak_signal = 180.0 if self._settings.pixel_format == "Mono8" else 2400.0
        background = 18.0 if self._settings.pixel_format == "Mono8" else 160.0
        gaussian = peak_signal * np.exp(
            -0.5 * ((x_rot / sigma_x) ** 2 + (y_rot / sigma_y) ** 2)
        )
        low_freq_gradient = 0.015 * x_idx + 0.02 * y_idx
        shot_noise = self._rng.normal(scale=max(1.0, peak_signal * 0.015), size=(height, width))
        frame = background + low_freq_gradient + gaussian + shot_noise

        if self._settings.pixel_format == "Mono8":
            image = np.clip(frame, 0.0, 255.0).astype(np.uint8)
        else:
            image = np.clip(frame, 0.0, 4095.0).astype(np.uint16)

        self._frame_index += 1
        return FramePacket(
            frame_index=self._frame_index,
            timestamp_s=timestamp_s,
            image=image,
        )


class BaslerCameraBackend(BaseCameraBackend):
    """pypylon-backed Basler acquisition interface."""

    name = "Basler"

    def __init__(self) -> None:
        self._camera = None
        self._frame_index = 0

    def connect(self, serial_number: str = "") -> str:
        if pylon is None or genicam is None:
            raise CameraBackendError(
                "pypylon is not installed. Install it to enable Basler acquisition."
            )
        factory = pylon.TlFactory.GetInstance()
        devices = list(factory.EnumerateDevices())
        if not devices:
            raise CameraBackendError("No Basler cameras were detected.")
        selected = None
        if serial_number:
            for device in devices:
                if device.GetSerialNumber() == serial_number:
                    selected = device
                    break
            if selected is None:
                raise CameraBackendError(
                    f"Basler serial number {serial_number!r} was not found."
                )
        else:
            selected = devices[0]
        self._camera = pylon.InstantCamera(factory.CreateDevice(selected))
        self._camera.Open()
        self._frame_index = 0
        return f"{selected.GetModelName()} ({selected.GetSerialNumber()})"

    def disconnect(self) -> None:
        if self._camera is not None:
            if self._camera.IsGrabbing():
                self._camera.StopGrabbing()
            if self._camera.IsOpen():
                self._camera.Close()
        self._camera = None

    def _require_camera(self):
        if self._camera is None:
            raise CameraBackendError("Camera is not connected.")
        return self._camera

    @staticmethod
    def _node_min(node):
        return node.Min if hasattr(node, "Min") else node.GetMin()

    @staticmethod
    def _node_max(node):
        return node.Max if hasattr(node, "Max") else node.GetMax()

    @staticmethod
    def _node_inc(node):
        if hasattr(node, "Inc"):
            return node.Inc
        if hasattr(node, "GetInc"):
            return node.GetInc()
        return 1

    def _set_integer_node(self, node_name: str, value: int) -> int | None:
        camera = self._require_camera()
        node = getattr(camera, node_name, None)
        if node is None or not genicam.IsWritable(node):
            return None
        minimum = int(self._node_min(node))
        maximum = int(self._node_max(node))
        increment = max(1, int(self._node_inc(node)))
        clipped = max(minimum, min(maximum, int(value)))
        aligned = minimum + ((clipped - minimum) // increment) * increment
        node.SetValue(aligned)
        return int(node.Value)

    def _set_float_node(self, node_name: str, value: float) -> float | None:
        camera = self._require_camera()
        node = getattr(camera, node_name, None)
        if node is None or not genicam.IsWritable(node):
            return None
        minimum = float(self._node_min(node))
        maximum = float(self._node_max(node))
        clipped = max(minimum, min(maximum, float(value)))
        node.SetValue(clipped)
        return float(node.Value)

    def _set_enum_node(self, node_name: str, value: str) -> str | None:
        camera = self._require_camera()
        node = getattr(camera, node_name, None)
        if node is None or not genicam.IsWritable(node):
            return None
        try:
            node.SetValue(value)
            return str(node.Value)
        except Exception:
            return None

    def apply_settings(self, settings: CameraSettings) -> CameraSettings:
        camera = self._require_camera()
        if camera.IsGrabbing():
            camera.StopGrabbing()

        self._set_enum_node("AcquisitionMode", "Continuous")
        self._set_enum_node("TriggerSelector", "FrameStart")
        self._set_enum_node("TriggerMode", "Off")

        pixel_format = self._set_enum_node("PixelFormat", settings.pixel_format)
        width = self._set_integer_node("Width", settings.width)
        height = self._set_integer_node("Height", settings.height)
        offset_x = self._set_integer_node("OffsetX", settings.offset_x)
        offset_y = self._set_integer_node("OffsetY", settings.offset_y)

        exposure = self._set_float_node("ExposureTime", settings.exposure_us)
        gain = self._set_float_node("Gain", settings.gain_db)

        frame_rate = None
        if hasattr(camera, "AcquisitionFrameRateEnable"):
            enable_node = getattr(camera, "AcquisitionFrameRateEnable")
            if genicam.IsWritable(enable_node):
                enable_node.SetValue(True)
        frame_rate = self._set_float_node("AcquisitionFrameRate", settings.frame_rate_fps)
        if frame_rate is None:
            frame_rate = self._set_float_node("AcquisitionFrameRateAbs", settings.frame_rate_fps)

        applied = CameraSettings(
            exposure_us=exposure if exposure is not None else settings.exposure_us,
            gain_db=gain if gain is not None else settings.gain_db,
            frame_rate_fps=frame_rate if frame_rate is not None else settings.frame_rate_fps,
            pixel_format=pixel_format or settings.pixel_format,
            width=width if width is not None else settings.width,
            height=height if height is not None else settings.height,
            offset_x=offset_x if offset_x is not None else settings.offset_x,
            offset_y=offset_y if offset_y is not None else settings.offset_y,
            serial_number=settings.serial_number,
        )
        self._frame_index = 0
        return applied

    def start_grabbing(self) -> None:
        camera = self._require_camera()
        if not camera.IsGrabbing():
            camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

    def stop_grabbing(self) -> None:
        camera = self._require_camera()
        if camera.IsGrabbing():
            camera.StopGrabbing()

    def retrieve_frame(self, timeout_ms: int = 1000) -> FramePacket:
        camera = self._require_camera()
        try:
            grab_result = camera.RetrieveResult(
                timeout_ms,
                pylon.TimeoutHandling_ThrowException,
            )
        except genicam.TimeoutException as exc:
            raise CameraTimeoutError(
                f"Frame grab timed out after {timeout_ms} ms. \
Check trigger mode, frame-rate settings, and camera transport."
            ) from exc
        try:
            if not grab_result.GrabSucceeded():
                raise CameraBackendError(grab_result.ErrorDescription)
            image = grab_result.Array.copy()
        finally:
            grab_result.Release()

        self._frame_index += 1
        return FramePacket(
            frame_index=self._frame_index,
            timestamp_s=time.perf_counter(),
            image=image,
        )
