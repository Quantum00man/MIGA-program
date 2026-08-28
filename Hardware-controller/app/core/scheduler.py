import threading
from datetime import datetime

import config


class HardwareScheduler:
    def __init__(self, controller_manager):
        self.controller_manager = controller_manager
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False
        self._last_trigger: dict[tuple, str] = {}

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="hardware-scheduler", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None

    def status(self) -> dict:
        return {
            "active": self._running,
            "interval_sec": config.SCHEDULER_INTERVAL_SEC,
            "last_keys": list(self._last_trigger.keys())[-10:],
        }

    def _loop(self):
        while not self._stop_event.is_set():
            try:
                self._tick_once()
            except Exception as exc:
                self.controller_manager.publish_event(
                    "error",
                    f"Scheduler loop error: {exc}",
                    category="scheduler",
                )
            self._stop_event.wait(config.SCHEDULER_INTERVAL_SEC)

    def _tick_once(self):
        now = datetime.now()
        state = self.controller_manager.store.get_state()
        self._tick_edfa(now, state.get("edfa_devices", []))
        self._tick_psu(now, state.get("psu_devices", []))

    def _tick_edfa(self, now: datetime, devices: list[dict]):
        today_key = now.date().isoformat()
        for device in devices:
            schedule = device.get("schedule") or {}
            if not schedule.get("enabled"):
                continue
            if now.weekday() not in set(schedule.get("days") or []):
                continue

            on_time = str(schedule.get("on_time") or "").strip()
            off_time = str(schedule.get("off_time") or "").strip()

            if self._matches(now, on_time):
                key = ("edfa", device["id"], "on")
                if self._last_trigger.get(key) != today_key:
                    if device.get("device_type") == "bragg_cefa":
                        self.controller_manager.set_bragg_edfa_output(device["id"], True, source="schedule")
                    else:
                        self.controller_manager.turn_edfa_device_on(device["id"], source="schedule")
                    self._last_trigger[key] = today_key

            if self._matches(now, off_time):
                key = ("edfa", device["id"], "off")
                if self._last_trigger.get(key) != today_key:
                    if device.get("device_type") == "bragg_cefa":
                        self.controller_manager.set_bragg_edfa_output(device["id"], False, source="schedule")
                    else:
                        self.controller_manager.turn_edfa_device_off(device["id"], source="schedule")
                    self._last_trigger[key] = today_key

    def _tick_psu(self, now: datetime, devices: list[dict]):
        today_key = now.date().isoformat()
        for device in devices:
            schedule = device.get("schedule") or {}
            channel_map = schedule.get("channels") if isinstance(schedule.get("channels"), dict) else {}
            for channel in config.PSU_CHANNELS:
                channel_schedule = channel_map.get(channel) if isinstance(channel_map.get(channel), dict) else {}
                if not channel_schedule.get("enabled"):
                    continue
                if now.weekday() not in set(channel_schedule.get("days") or []):
                    continue

                on_time = str(channel_schedule.get("on_time") or "").strip()
                off_time = str(channel_schedule.get("off_time") or "").strip()

                if self._matches(now, on_time):
                    key = ("psu", device["id"], channel, "on")
                    if self._last_trigger.get(key) != today_key:
                        self.controller_manager.set_psu_channel_output(
                            device["id"],
                            int(channel),
                            True,
                            source="schedule",
                        )
                        self._last_trigger[key] = today_key

                if self._matches(now, off_time):
                    key = ("psu", device["id"], channel, "off")
                    if self._last_trigger.get(key) != today_key:
                        self.controller_manager.set_psu_channel_output(
                            device["id"],
                            int(channel),
                            False,
                            source="schedule",
                        )
                        self._last_trigger[key] = today_key

    @staticmethod
    def _matches(now: datetime, time_text: str) -> bool:
        if not time_text:
            return False
        return now.strftime("%H:%M") == time_text and now.second <= 1
