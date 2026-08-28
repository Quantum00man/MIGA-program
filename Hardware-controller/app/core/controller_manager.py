from collections import deque
from copy import deepcopy
from datetime import datetime
import socket
from threading import RLock
from uuid import uuid4

import config
from app.core.scheduler import HardwareScheduler
from app.core.state_store import StateStore
from app.drivers.bragg_edfa import (
    BraggEdfaClient,
    BraggEdfaCommunicationError,
    available_ports as available_bragg_ports,
)
from app.drivers.edfa import EdfaCommunicationError, probe_device as probe_edfa_device, send_commands
from app.drivers.laser_lock import (
    LASER_CHANNELS,
    LaserLockCommunicationError,
    LaserLockSession,
)
from app.drivers.psu import PsuClient, PsuCommunicationError


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _normalize_days(values, default):
    if not isinstance(values, list):
        return list(default)
    normalized = []
    for value in values:
        try:
            day = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= day <= 6 and day not in normalized:
            normalized.append(day)
    return normalized or list(default)


def _find_in_collection(collection: list[dict], device_id: str) -> dict:
    for device in collection:
        if device.get("id") == device_id:
            return device
    raise ValueError(f"Device {device_id} was not found.")


class ControllerManager:
    def __init__(self, store: StateStore):
        self.store = store
        self.scheduler = HardwareScheduler(self)
        self._event_callback = None
        self._event_log = deque(maxlen=config.MAX_EVENT_LOG)
        self._io_lock = RLock()
        self._psu_clients: dict[str, PsuClient] = {}
        self._bragg_clients: dict[str, BraggEdfaClient] = {}
        self._laser_sessions = {
            key: LaserLockSession(key, max_output_lines=config.LASER_LOCK_OUTPUT_LINES)
            for key in LASER_CHANNELS
        }

    def start(self):
        self.scheduler.start()
        self.publish_event("info", "Hardware controller service started.", category="system")

    def stop(self):
        self.scheduler.stop()
        for session in self._laser_sessions.values():
            session.stop(send_interrupt=False)
        with self._io_lock:
            for client in self._bragg_clients.values():
                client.close()
            self._bragg_clients.clear()
            for client in self._psu_clients.values():
                client.close()
            self._psu_clients.clear()
        self.publish_event("info", "Hardware controller service stopped.", category="system")

    def set_event_callback(self, callback):
        self._event_callback = callback

    def publish_event(self, level: str, message: str, category: str = "system", device_id: str | None = None):
        event = {
            "type": "event",
            "level": level,
            "message": message,
            "category": category,
            "device_id": device_id,
            "timestamp": _now_iso(),
        }
        self._event_log.appendleft(event)
        if self._event_callback:
            self._event_callback(event)

    def notify_state_changed(self):
        if self._event_callback:
            self._event_callback({"type": "state", "timestamp": _now_iso()})

    def get_public_state(self) -> dict:
        state = self.store.get_state()
        state.pop("auth", None)
        return {
            "app": {
                "title": config.APP_TITLE,
                "version": config.APP_VERSION,
            },
            "state": state,
            "runtime": {
                "events": list(self._event_log),
                "scheduler": self.scheduler.status(),
                "laser_locks": {
                    key: session.snapshot()
                    for key, session in self._laser_sessions.items()
                },
                "generated_at": _now_iso(),
            },
        }

    @staticmethod
    def normalize_time_text(value, allow_blank: bool = True) -> str:
        text = str(value or "").strip().replace("：", ":")
        if not text:
            if allow_blank:
                return ""
            raise ValueError("A time value is required.")

        if ":" not in text and text.isdigit():
            if len(text) in (1, 2):
                hour = int(text)
                minute = 0
            elif len(text) == 3:
                hour = int(text[0])
                minute = int(text[1:])
            elif len(text) == 4:
                hour = int(text[:2])
                minute = int(text[2:])
            else:
                raise ValueError("Time must follow HH:MM format.")
        else:
            parts = text.split(":")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError("Time must follow HH:MM format.")
            hour = int(parts[0])
            minute = int(parts[1])

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Time must be within 00:00 and 23:59.")
        return f"{hour:02d}:{minute:02d}"

    @staticmethod
    def _coerce_port(value, default_port: int) -> int:
        try:
            port = int(value)
        except (TypeError, ValueError):
            port = default_port
        if not (1 <= port <= 65535):
            raise ValueError("Port must be between 1 and 65535.")
        return port

    @staticmethod
    def _coerce_float(value, default_value: float, field_name: str, minimum: float = 0.0) -> float:
        try:
            coerced = float(value)
        except (TypeError, ValueError):
            coerced = default_value
        if coerced < minimum:
            raise ValueError(f"{field_name} must be at least {minimum}.")
        return coerced

    def _build_edfa_device(self, payload: dict, existing: dict | None = None) -> dict:
        existing = deepcopy(existing or {})
        device_type = str(payload.get("device_type") or existing.get("device_type") or "network_edfa")
        if device_type == "bragg_cefa":
            return self._build_bragg_edfa_device(payload, existing)
        if device_type != "network_edfa":
            raise ValueError(f"Unknown EDFA device type {device_type}.")
        name = str(payload.get("name") or existing.get("name") or self.store.next_device_name("edfa")).strip()
        ip = str(payload.get("ip") or existing.get("ip") or "").strip()
        if not ip:
            raise ValueError("EDFA IP address is required.")

        port = self._coerce_port(payload.get("port"), existing.get("port", config.EDFA_DEFAULT_PORT))
        timeout_sec = self._coerce_float(
            payload.get("timeout_sec"),
            existing.get("timeout_sec", config.NETWORK_TIMEOUT_SEC),
            "Timeout",
            minimum=0.1,
        )
        command_delay_sec = self._coerce_float(
            payload.get("command_delay_sec"),
            existing.get("command_delay_sec", config.EDFA_COMMAND_DELAY_SEC),
            "Command delay",
            minimum=0.0,
        )

        existing_channels = {
            channel["key"]: channel
            for channel in existing.get("channels", [])
            if isinstance(channel, dict) and channel.get("key")
        }
        payload_channels = payload.get("channels") if isinstance(payload.get("channels"), list) else []
        payload_channel_map = {
            str(channel.get("key") or ""): channel
            for channel in payload_channels
            if isinstance(channel, dict) and channel.get("key")
        }
        channels = []
        for key in config.EDFA_CHANNEL_KEYS:
            source = payload_channel_map.get(key, {})
            previous = existing_channels.get(key, {})
            default_power = config.EDFA_DEFAULT_POWERS[key]
            channels.append(
                {
                    "key": key,
                    "label": str(source.get("label") or previous.get("label") or key.upper()).strip() or key.upper(),
                    "power": str(source.get("power") or previous.get("power") or default_power).strip() or default_power,
                    "assumed_on": bool(previous.get("assumed_on", False)),
                }
            )

        existing_schedule = existing.get("schedule") if isinstance(existing.get("schedule"), dict) else {}
        schedule_input = payload.get("schedule") if isinstance(payload.get("schedule"), dict) else {}
        schedule = {
            "enabled": bool(schedule_input.get("enabled", existing_schedule.get("enabled", False))),
            "days": _normalize_days(
                schedule_input.get("days", existing_schedule.get("days", config.DEFAULT_WEEKDAYS)),
                config.DEFAULT_WEEKDAYS,
            ),
            "on_time": self.normalize_time_text(
                schedule_input.get("on_time", existing_schedule.get("on_time", "08:00")),
                allow_blank=True,
            ),
            "off_time": self.normalize_time_text(
                schedule_input.get("off_time", existing_schedule.get("off_time", "18:00")),
                allow_blank=True,
            ),
        }
        if schedule["enabled"] and not schedule["on_time"] and not schedule["off_time"]:
            raise ValueError("An enabled EDFA schedule requires at least one ON or OFF time.")

        return {
            "id": str(payload.get("id") or existing.get("id") or uuid4().hex[:8]),
            "device_type": "network_edfa",
            "name": name,
            "ip": ip,
            "port": port,
            "timeout_sec": timeout_sec,
            "command_delay_sec": command_delay_sec,
            "channels": channels,
            "schedule": schedule,
            "notes": str(payload.get("notes") or existing.get("notes") or "").strip(),
            "reachable": existing.get("reachable"),
            "last_action": existing.get("last_action", "No action yet"),
            "last_error": existing.get("last_error", ""),
            "last_contact_at": existing.get("last_contact_at", ""),
        }

    def _build_psu_device(self, payload: dict, existing: dict | None = None) -> dict:
        existing = deepcopy(existing or {})
        name = str(payload.get("name") or existing.get("name") or self.store.next_device_name("psu")).strip()
        ip = str(payload.get("ip") or existing.get("ip") or "").strip()
        if not ip:
            raise ValueError("PSU IP address is required.")

        port = self._coerce_port(payload.get("port"), existing.get("port", config.PSU_DEFAULT_PORT))
        timeout_sec = self._coerce_float(
            payload.get("timeout_sec"),
            existing.get("timeout_sec", config.NETWORK_TIMEOUT_SEC),
            "Timeout",
            minimum=0.1,
        )

        existing_schedule = existing.get("schedule") if isinstance(existing.get("schedule"), dict) else {}
        existing_channels = existing_schedule.get("channels") if isinstance(existing_schedule.get("channels"), dict) else {}
        payload_schedule = payload.get("schedule") if isinstance(payload.get("schedule"), dict) else {}
        payload_channels = payload_schedule.get("channels") if isinstance(payload_schedule.get("channels"), dict) else {}

        schedule_channels = {}
        for channel_key in config.PSU_CHANNELS:
            previous = existing_channels.get(channel_key) if isinstance(existing_channels.get(channel_key), dict) else {}
            incoming = payload_channels.get(channel_key) if isinstance(payload_channels.get(channel_key), dict) else {}
            schedule_channels[channel_key] = {
                "enabled": bool(incoming.get("enabled", previous.get("enabled", False))),
                "days": _normalize_days(
                    incoming.get("days", previous.get("days", config.DEFAULT_WEEKDAYS)),
                    config.DEFAULT_WEEKDAYS,
                ),
                "on_time": self.normalize_time_text(
                    incoming.get("on_time", previous.get("on_time", "")),
                    allow_blank=True,
                ),
                "off_time": self.normalize_time_text(
                    incoming.get("off_time", previous.get("off_time", "")),
                    allow_blank=True,
                ),
            }
            channel_schedule = schedule_channels[channel_key]
            if channel_schedule["enabled"] and not channel_schedule["on_time"] and not channel_schedule["off_time"]:
                raise ValueError(
                    f"PSU channel {channel_key} schedule is enabled but no ON/OFF time was provided."
                )

        return {
            "id": str(payload.get("id") or existing.get("id") or uuid4().hex[:8]),
            "name": name,
            "ip": ip,
            "port": port,
            "timeout_sec": timeout_sec,
            "schedule": {"channels": schedule_channels},
            "notes": str(payload.get("notes") or existing.get("notes") or "").strip(),
            "connected": bool(existing.get("connected", False)),
            "reachable": existing.get("reachable"),
            "idn": str(existing.get("idn") or ""),
            "config_mode": str(existing.get("config_mode") or ""),
            "channel_states": {
                "1": str((existing.get("channel_states") or {}).get("1") or "unknown"),
                "2": str((existing.get("channel_states") or {}).get("2") or "unknown"),
            },
            "last_action": existing.get("last_action", "No action yet"),
            "last_error": existing.get("last_error", ""),
            "last_contact_at": existing.get("last_contact_at", ""),
        }

    def _build_bragg_edfa_device(self, payload: dict, existing: dict) -> dict:
        name = str(payload.get("name") or existing.get("name") or "Bragg CEFA EDFA").strip()
        serial_port = str(payload.get("serial_port") or existing.get("serial_port") or "").strip()
        timeout_sec = self._coerce_float(
            payload.get("timeout_sec"),
            existing.get("timeout_sec", 0.8),
            "Timeout",
            minimum=0.1,
        )
        setpoint = self._coerce_float(
            payload.get("apc_setpoint_dbm"),
            existing.get("apc_setpoint_dbm", 33.0),
            "APC setpoint",
            minimum=0.0,
        )
        if setpoint > 33.0:
            raise ValueError("APC setpoint must not exceed 33 dBm.")
        existing_schedule = existing.get("schedule") if isinstance(existing.get("schedule"), dict) else {}
        schedule_input = payload.get("schedule") if isinstance(payload.get("schedule"), dict) else {}
        schedule = {
            "enabled": bool(schedule_input.get("enabled", existing_schedule.get("enabled", False))),
            "days": _normalize_days(
                schedule_input.get("days", existing_schedule.get("days", config.DEFAULT_WEEKDAYS)),
                config.DEFAULT_WEEKDAYS,
            ),
            "on_time": self.normalize_time_text(
                schedule_input.get("on_time", existing_schedule.get("on_time", "08:00")),
                allow_blank=True,
            ),
            "off_time": self.normalize_time_text(
                schedule_input.get("off_time", existing_schedule.get("off_time", "18:00")),
                allow_blank=True,
            ),
        }
        if schedule["enabled"] and not schedule["on_time"] and not schedule["off_time"]:
            raise ValueError("An enabled Bragg EDFA schedule requires at least one ON or OFF time.")
        return {
            "id": str(payload.get("id") or existing.get("id") or uuid4().hex[:8]),
            "device_type": "bragg_cefa",
            "name": name or "Bragg CEFA EDFA",
            "ip": "",
            "serial_port": serial_port,
            "port": config.EDFA_DEFAULT_PORT,
            "timeout_sec": timeout_sec,
            "command_delay_sec": 0.0,
            "apc_setpoint_dbm": setpoint,
            "channels": [],
            "schedule": schedule,
            "notes": str(payload.get("notes") or existing.get("notes") or "").strip(),
            "connected": bool(existing.get("connected", False)),
            "reachable": existing.get("reachable"),
            "serial_number": str(existing.get("serial_number") or ""),
            "input_power": deepcopy(existing.get("input_power") or {}),
            "output_power": deepcopy(existing.get("output_power") or {}),
            "output_mode": str(existing.get("output_mode") or ""),
            "output_state": str(existing.get("output_state") or "UNKNOWN"),
            "last_action": existing.get("last_action", "No action yet"),
            "last_error": existing.get("last_error", ""),
            "last_contact_at": existing.get("last_contact_at", ""),
        }

    def save_laser_lock_system(self, payload: dict) -> dict:
        current = self.store.get_state().get("laser_lock_system", {})
        name = str(payload.get("name") or current.get("name") or "MIGA2 Laser Lock").strip()
        ip = str(payload.get("ip") or "").strip()
        if not ip:
            raise ValueError("Laser lock IP address is required.")
        port = self._coerce_port(payload.get("port"), current.get("port", config.LASER_LOCK_DEFAULT_PORT))
        timeout_sec = self._coerce_float(
            payload.get("timeout_sec"),
            current.get("timeout_sec", config.NETWORK_TIMEOUT_SEC),
            "Timeout",
            minimum=0.1,
        )
        system = {
            "name": name or "MIGA2 Laser Lock",
            "ip": ip,
            "port": port,
            "timeout_sec": timeout_sec,
            "notes": str(payload.get("notes") or "").strip(),
        }

        before_connection = (
            current.get("ip"),
            current.get("port"),
            current.get("timeout_sec"),
        )
        after_connection = (ip, port, timeout_sec)
        if before_connection != after_connection:
            for session in self._laser_sessions.values():
                if session.is_running:
                    session.stop(send_interrupt=True)

        def mutator(state: dict):
            state["laser_lock_system"] = system

        self.store.update(mutator)
        self.publish_event(
            "info",
            f"Saved laser lock controller {system['name']} ({ip}:{port}).",
            category="laser_lock",
        )
        self.notify_state_changed()
        return system

    def probe_laser_lock_system(self):
        system = self.store.get_state().get("laser_lock_system", {})
        if not system.get("ip"):
            raise ValueError("Configure the laser lock IP address first.")
        try:
            with socket.create_connection(
                (system["ip"], int(system["port"])),
                timeout=float(system["timeout_sec"]),
            ):
                pass
            self.publish_event(
                "info",
                f"Laser lock controller responded at {system['ip']}:{system['port']}.",
                category="laser_lock",
            )
        except OSError as exc:
            message = (
                f"Failed to connect to laser lock controller at "
                f"{system['ip']}:{system['port']}: {exc}"
            )
            self.publish_event("error", message, category="laser_lock")
            raise LaserLockCommunicationError(message) from exc

    def start_laser_lock_channel(self, channel_key: str, relock: bool = False):
        if channel_key not in self._laser_sessions:
            raise ValueError(f"Unknown laser lock channel {channel_key}.")
        system = self.store.get_state().get("laser_lock_system", {})
        if not system.get("ip"):
            raise ValueError("Configure the laser lock IP address first.")

        session = self._laser_sessions[channel_key]
        session.start(
            system["ip"],
            int(system["port"]),
            float(system["timeout_sec"]),
            relock=relock,
        )
        action = "relock" if relock else "start lock"
        self.publish_event(
            "warning" if relock else "info",
            f"{LASER_CHANNELS[channel_key]['label']}: requested {action}.",
            category="laser_lock",
            device_id=channel_key,
        )
        self.notify_state_changed()

    def disconnect_all_telnet_sessions(self) -> dict:
        disconnected_laser_channels = []
        for channel_key, session in self._laser_sessions.items():
            snapshot = session.snapshot()
            if session.is_running or snapshot["connected"]:
                session.stop(send_interrupt=False)
                disconnected_laser_channels.append(channel_key)

        # EDFA commands use short-lived sockets. Taking the shared I/O lock
        # guarantees any command already in progress has completed and closed
        # its socket before this action returns.
        with self._io_lock:
            pass

        self.publish_event(
            "warning",
            "Disconnected all Telnet sessions. EDFA command sockets are closed after every command.",
            category="telnet",
        )
        self.notify_state_changed()
        return {
            "laser_channels_disconnected": disconnected_laser_channels,
            "edfa_persistent_connections": 0,
        }

    def add_edfa_device(self, payload: dict) -> dict:
        device = self._build_edfa_device(payload)

        def mutator(state: dict):
            state["edfa_devices"].append(device)

        self.store.update(mutator)
        self.publish_event("info", f"Added EDFA device {device['name']} ({device['ip']}).", category="edfa", device_id=device["id"])
        self.notify_state_changed()
        return device

    def update_edfa_device(self, device_id: str, payload: dict) -> dict:
        state = self.store.get_state()
        existing = _find_in_collection(state["edfa_devices"], device_id)
        device = self._build_edfa_device({**payload, "id": device_id}, existing=existing)
        bragg_connection_changed = existing.get("device_type") == "bragg_cefa" and (
            existing.get("serial_port"), existing.get("timeout_sec")
        ) != (device.get("serial_port"), device.get("timeout_sec"))
        if bragg_connection_changed:
            device["connected"] = False

        def mutator(state_mut: dict):
            target = _find_in_collection(state_mut["edfa_devices"], device_id)
            target.clear()
            target.update(device)

        self.store.update(mutator)
        if bragg_connection_changed:
            self._close_bragg_client(device_id)
        self.publish_event("info", f"Updated EDFA device {device['name']}.", category="edfa", device_id=device_id)
        self.notify_state_changed()
        return device

    def delete_edfa_device(self, device_id: str):
        self._close_bragg_client(device_id)

        def mutator(state: dict):
            state["edfa_devices"] = [device for device in state["edfa_devices"] if device.get("id") != device_id]

        self.store.update(mutator)
        self.publish_event("warning", f"Removed EDFA device {device_id}.", category="edfa", device_id=device_id)
        self.notify_state_changed()

    def _close_bragg_client(self, device_id: str):
        with self._io_lock:
            client = self._bragg_clients.pop(device_id, None)
            if client:
                client.close()

    def _get_bragg_client(self, device: dict) -> BraggEdfaClient:
        if device.get("device_type") != "bragg_cefa":
            raise ValueError("This action is only available for Bragg/CEFA EDFA devices.")
        if not device.get("serial_port"):
            raise ValueError("Select and save a COM port first.")
        device_id = device["id"]
        client = self._bragg_clients.get(device_id)
        if client and (
            client.port_name != device["serial_port"]
            or client.timeout_sec != device["timeout_sec"]
        ):
            client.close()
            client = None
            self._bragg_clients.pop(device_id, None)
        if client is None:
            client = BraggEdfaClient(device["serial_port"], device["timeout_sec"])
            self._bragg_clients[device_id] = client
        return client

    def list_bragg_edfa_ports(self) -> list[dict]:
        return available_bragg_ports()

    def connect_bragg_edfa(self, device_id: str):
        device = _find_in_collection(self.store.get_state()["edfa_devices"], device_id)
        try:
            with self._io_lock:
                client = self._get_bragg_client(device)
                serial_number = client.connect()
                readings = client.read_state()
            self._update_edfa_runtime(
                device_id,
                lambda target: target.update({
                    "connected": True, "reachable": True, "serial_number": serial_number,
                    **readings, "last_error": "", "last_contact_at": _now_iso(),
                    "last_action": "Serial connection established and state refreshed",
                }),
            )
            self.publish_event("info", f"{device['name']}: connected on {device['serial_port']} (SN {serial_number}).", category="edfa", device_id=device_id)
        except BraggEdfaCommunicationError as exc:
            self._close_bragg_client(device_id)
            self._update_edfa_runtime(device_id, lambda target: target.update({
                "connected": False, "reachable": False, "last_error": str(exc),
                "last_contact_at": _now_iso(), "last_action": "Serial connection failed",
            }))
            raise

    def disconnect_bragg_edfa(self, device_id: str):
        device = _find_in_collection(self.store.get_state()["edfa_devices"], device_id)
        if device.get("device_type") != "bragg_cefa":
            raise ValueError("This is not a Bragg/CEFA EDFA device.")
        self._close_bragg_client(device_id)
        self._update_edfa_runtime(device_id, lambda target: target.update({
            "connected": False, "last_action": "Serial connection closed", "last_error": "",
        }))

    def refresh_bragg_edfa(self, device_id: str):
        device = _find_in_collection(self.store.get_state()["edfa_devices"], device_id)
        try:
            with self._io_lock:
                client = self._get_bragg_client(device)
                if not client.connected:
                    raise BraggEdfaCommunicationError("Connect the Bragg EDFA before refreshing it.")
                readings = client.read_state()
            self._update_edfa_runtime(device_id, lambda target: target.update({
                "connected": True, "reachable": True, **readings, "last_error": "",
                "last_contact_at": _now_iso(), "last_action": "Power and output state refreshed",
            }))
        except BraggEdfaCommunicationError as exc:
            self._update_edfa_runtime(device_id, lambda target: target.update({
                "connected": False, "reachable": False, "last_error": str(exc),
                "last_contact_at": _now_iso(), "last_action": "State refresh failed",
            }))
            raise

    def set_bragg_edfa_setpoint(self, device_id: str, value_dbm: float):
        device = _find_in_collection(self.store.get_state()["edfa_devices"], device_id)
        with self._io_lock:
            client = self._get_bragg_client(device)
            client.set_apc_setpoint(float(value_dbm))
        self._update_edfa_runtime(device_id, lambda target: target.update({
            "apc_setpoint_dbm": float(value_dbm), "reachable": True, "last_error": "",
            "last_contact_at": _now_iso(), "last_action": f"APC setpoint changed to {float(value_dbm):.1f} dBm",
        }))
        self.publish_event("warning", f"{device['name']}: APC setpoint changed to {float(value_dbm):.1f} dBm.", category="edfa", device_id=device_id)

    def set_bragg_edfa_output(self, device_id: str, turn_on: bool, source: str = "manual"):
        device = _find_in_collection(self.store.get_state()["edfa_devices"], device_id)
        with self._io_lock:
            client = self._get_bragg_client(device)
            serial_number = device.get("serial_number", "")
            if not client.connected:
                serial_number = client.connect()
            client.set_output(turn_on)
            readings = client.read_state()
        action = "ON in APC mode" if turn_on else "OFF"
        self._update_edfa_runtime(device_id, lambda target: target.update({
            "connected": True, "reachable": True, **readings, "last_error": "",
            "serial_number": serial_number,
            "last_contact_at": _now_iso(), "last_action": f"Optical output switched {action} ({source})",
        }))
        self.publish_event("warning", f"{device['name']}: optical output switched {action} ({source}).", category="edfa", device_id=device_id)

    def add_psu_device(self, payload: dict) -> dict:
        device = self._build_psu_device(payload)

        def mutator(state: dict):
            state["psu_devices"].append(device)

        self.store.update(mutator)
        self.publish_event("info", f"Added PSU device {device['name']} ({device['ip']}).", category="psu", device_id=device["id"])
        self.notify_state_changed()
        return device

    def update_psu_device(self, device_id: str, payload: dict) -> dict:
        state = self.store.get_state()
        existing = _find_in_collection(state["psu_devices"], device_id)
        before_key = (existing["ip"], existing["port"], existing["timeout_sec"])
        device = self._build_psu_device({**payload, "id": device_id}, existing=existing)
        after_key = (device["ip"], device["port"], device["timeout_sec"])

        def mutator(state_mut: dict):
            target = _find_in_collection(state_mut["psu_devices"], device_id)
            target.clear()
            target.update(device)

        self.store.update(mutator)
        if before_key != after_key:
            self._close_psu_client(device_id)
        self.publish_event("info", f"Updated PSU device {device['name']}.", category="psu", device_id=device_id)
        self.notify_state_changed()
        return device

    def delete_psu_device(self, device_id: str):
        self._close_psu_client(device_id)

        def mutator(state: dict):
            state["psu_devices"] = [device for device in state["psu_devices"] if device.get("id") != device_id]

        self.store.update(mutator)
        self.publish_event("warning", f"Removed PSU device {device_id}.", category="psu", device_id=device_id)
        self.notify_state_changed()

    def _close_psu_client(self, device_id: str):
        with self._io_lock:
            client = self._psu_clients.pop(device_id, None)
            if client:
                client.close()

    def _get_psu_client(self, device: dict) -> PsuClient:
        device_id = device["id"]
        client = self._psu_clients.get(device_id)
        if client and (
            client.ip != device["ip"]
            or client.port != device["port"]
            or client.timeout_sec != device["timeout_sec"]
        ):
            client.close()
            client = None
            self._psu_clients.pop(device_id, None)

        if client is None:
            client = PsuClient(device["ip"], device["port"], device["timeout_sec"])
            self._psu_clients[device_id] = client
        return client

    def _update_edfa_runtime(self, device_id: str, updater):
        def mutator(state: dict):
            device = _find_in_collection(state["edfa_devices"], device_id)
            updater(device)

        self.store.update(mutator)
        self.notify_state_changed()

    def _update_psu_runtime(self, device_id: str, updater):
        def mutator(state: dict):
            device = _find_in_collection(state["psu_devices"], device_id)
            updater(device)

        self.store.update(mutator)
        self.notify_state_changed()

    def probe_edfa_device(self, device_id: str):
        state = self.store.get_state()
        device = _find_in_collection(state["edfa_devices"], device_id)
        if device.get("device_type") == "bragg_cefa":
            self.connect_bragg_edfa(device_id)
            return
        try:
            with self._io_lock:
                probe_edfa_device(device["ip"], device["port"], device["timeout_sec"])
            self._update_edfa_runtime(
                device_id,
                lambda target: target.update(
                    {
                        "reachable": True,
                        "last_error": "",
                        "last_contact_at": _now_iso(),
                        "last_action": "Reachability probe succeeded",
                    }
                ),
            )
            self.publish_event("info", f"EDFA device {device['name']} responded to TCP probe.", category="edfa", device_id=device_id)
        except EdfaCommunicationError as exc:
            self._update_edfa_runtime(
                device_id,
                lambda target: target.update(
                    {
                        "reachable": False,
                        "last_error": str(exc),
                        "last_contact_at": _now_iso(),
                        "last_action": "Reachability probe failed",
                    }
                ),
            )
            self.publish_event("error", str(exc), category="edfa", device_id=device_id)
            raise

    def _run_edfa_commands(self, device: dict, commands: list[str]):
        with self._io_lock:
            send_commands(
                device["ip"],
                device["port"],
                device["timeout_sec"],
                device["command_delay_sec"],
                commands,
            )

    def set_edfa_channel_on(self, device_id: str, channel_key: str, power: str | None = None, source: str = "manual"):
        state = self.store.get_state()
        device = _find_in_collection(state["edfa_devices"], device_id)
        if device.get("device_type", "network_edfa") != "network_edfa":
            raise ValueError("Use the confirmed Bragg/CEFA output controls for this device.")
        channel_map = {item["key"]: item for item in device["channels"]}
        if channel_key not in channel_map:
            raise ValueError(f"Unknown EDFA channel {channel_key}.")
        target_channel = channel_map[channel_key]
        power_text = str(power or target_channel["power"]).strip() or target_channel["power"]
        command = f"driver_edfa_tool ctrl_phdout {channel_key} {power_text}"

        try:
            self._run_edfa_commands(device, [command])
            self._update_edfa_runtime(
                device_id,
                lambda target: self._mark_edfa_channel_state(
                    target,
                    channel_key,
                    True,
                    power_text,
                    f"{source.title()} ON {channel_key} -> {power_text}",
                    "",
                    True,
                ),
            )
            self.publish_event(
                "info",
                f"{device['name']}: {channel_key} set to {power_text} ({source}).",
                category="edfa",
                device_id=device_id,
            )
        except EdfaCommunicationError as exc:
            self._update_edfa_runtime(
                device_id,
                lambda target: target.update(
                    {
                        "reachable": False,
                        "last_error": str(exc),
                        "last_contact_at": _now_iso(),
                        "last_action": f"Failed to switch {channel_key} ON",
                    }
                ),
            )
            self.publish_event("error", str(exc), category="edfa", device_id=device_id)
            raise

    def set_edfa_channel_off(self, device_id: str, channel_key: str, source: str = "manual"):
        state = self.store.get_state()
        device = _find_in_collection(state["edfa_devices"], device_id)
        if device.get("device_type", "network_edfa") != "network_edfa":
            raise ValueError("Use the confirmed Bragg/CEFA output controls for this device.")
        channel_map = {item["key"]: item for item in device["channels"]}
        if channel_key not in channel_map:
            raise ValueError(f"Unknown EDFA channel {channel_key}.")
        commands = [
            f"driver_edfa_tool ctrl_phdout {channel_key} 0",
            f"driver_edfa_tool shutdown {channel_key}",
        ]

        try:
            self._run_edfa_commands(device, commands)
            self._update_edfa_runtime(
                device_id,
                lambda target: self._mark_edfa_channel_state(
                    target,
                    channel_key,
                    False,
                    channel_map[channel_key]["power"],
                    f"{source.title()} OFF {channel_key}",
                    "",
                    True,
                ),
            )
            self.publish_event(
                "info",
                f"{device['name']}: {channel_key} switched OFF ({source}).",
                category="edfa",
                device_id=device_id,
            )
        except EdfaCommunicationError as exc:
            self._update_edfa_runtime(
                device_id,
                lambda target: target.update(
                    {
                        "reachable": False,
                        "last_error": str(exc),
                        "last_contact_at": _now_iso(),
                        "last_action": f"Failed to switch {channel_key} OFF",
                    }
                ),
            )
            self.publish_event("error", str(exc), category="edfa", device_id=device_id)
            raise

    @staticmethod
    def _mark_edfa_channel_state(target: dict, channel_key: str, assumed_on: bool, power: str, last_action: str, last_error: str, reachable: bool):
        for channel in target["channels"]:
            if channel["key"] == channel_key:
                channel["assumed_on"] = assumed_on
                channel["power"] = power
                break
        target["reachable"] = reachable
        target["last_error"] = last_error
        target["last_contact_at"] = _now_iso()
        target["last_action"] = last_action

    def turn_edfa_device_on(self, device_id: str, source: str = "manual"):
        state = self.store.get_state()
        device = _find_in_collection(state["edfa_devices"], device_id)
        if device.get("device_type", "network_edfa") != "network_edfa":
            raise ValueError("Bragg/CEFA output cannot be enabled through network EDFA batch controls.")
        commands = [
            f"driver_edfa_tool ctrl_phdout {channel['key']} {channel['power']}"
            for channel in device["channels"]
        ]
        try:
            self._run_edfa_commands(device, commands)

            def updater(target: dict):
                for channel in target["channels"]:
                    channel["assumed_on"] = True
                target["reachable"] = True
                target["last_error"] = ""
                target["last_contact_at"] = _now_iso()
                target["last_action"] = f"{source.title()} START ALL EDFA"

            self._update_edfa_runtime(device_id, updater)
            self.publish_event(
                "info",
                f"{device['name']}: started all EDFA channels ({source}).",
                category="edfa",
                device_id=device_id,
            )
        except EdfaCommunicationError as exc:
            self._update_edfa_runtime(
                device_id,
                lambda target: target.update(
                    {
                        "reachable": False,
                        "last_error": str(exc),
                        "last_contact_at": _now_iso(),
                        "last_action": "Failed to start all EDFA channels",
                    }
                ),
            )
            self.publish_event("error", str(exc), category="edfa", device_id=device_id)
            raise

    def turn_edfa_device_off(self, device_id: str, source: str = "manual"):
        state = self.store.get_state()
        device = _find_in_collection(state["edfa_devices"], device_id)
        if device.get("device_type", "network_edfa") != "network_edfa":
            raise ValueError("Use the confirmed Bragg/CEFA OUTPUT OFF control for this device.")
        commands = [
            f"driver_edfa_tool ctrl_phdout {channel['key']} 0"
            for channel in device["channels"]
        ] + [
            f"driver_edfa_tool shutdown {channel['key']}"
            for channel in device["channels"]
        ]
        try:
            self._run_edfa_commands(device, commands)

            def updater(target: dict):
                for channel in target["channels"]:
                    channel["assumed_on"] = False
                target["reachable"] = True
                target["last_error"] = ""
                target["last_contact_at"] = _now_iso()
                target["last_action"] = f"{source.title()} SAFE SHUTDOWN ALL EDFA"

            self._update_edfa_runtime(device_id, updater)
            self.publish_event(
                "info",
                f"{device['name']}: shut down all EDFA channels ({source}).",
                category="edfa",
                device_id=device_id,
            )
        except EdfaCommunicationError as exc:
            self._update_edfa_runtime(
                device_id,
                lambda target: target.update(
                    {
                        "reachable": False,
                        "last_error": str(exc),
                        "last_contact_at": _now_iso(),
                        "last_action": "Failed to shut down all EDFA channels",
                    }
                ),
            )
            self.publish_event("error", str(exc), category="edfa", device_id=device_id)
            raise

    def run_edfa_batch(self, turn_on: bool, device_ids: list[str] | None = None):
        state = self.store.get_state()
        devices = state["edfa_devices"]
        selected_ids = set(device_ids or [])
        targets = [
            device for device in devices
            if device.get("device_type", "network_edfa") == "network_edfa"
            and (not selected_ids or device["id"] in selected_ids)
        ]
        if not targets:
            raise ValueError("No EDFA devices are available for the batch action.")

        failures = []
        for device in targets:
            try:
                if turn_on:
                    self.turn_edfa_device_on(device["id"], source="manual-batch")
                else:
                    self.turn_edfa_device_off(device["id"], source="manual-batch")
            except Exception as exc:
                failures.append(f"{device['name']}: {exc}")

        if failures:
            raise RuntimeError("Some EDFA batch actions failed: " + " | ".join(failures))

    def apply_edfa_template_to_all(self, payload: dict):
        state = self.store.get_state()
        selected_ids = set(payload.get("device_ids") or [])
        targets = [device for device in state["edfa_devices"] if not selected_ids or device["id"] in selected_ids]
        if not targets:
            raise ValueError("No EDFA devices are available for template application.")

        schedule_payload = payload.get("schedule") if isinstance(payload.get("schedule"), dict) else {}
        channel_payload = payload.get("channels") if isinstance(payload.get("channels"), list) else []
        updated_devices = []
        for device in targets:
            merged_payload = deepcopy(device)
            if schedule_payload:
                merged_payload["schedule"] = schedule_payload
            if channel_payload:
                merged_payload["channels"] = channel_payload
            updated_devices.append(self._build_edfa_device(merged_payload, existing=device))

        def mutator(state_mut: dict):
            device_map = {device["id"]: device for device in updated_devices}
            for index, device in enumerate(state_mut["edfa_devices"]):
                replacement = device_map.get(device["id"])
                if replacement:
                    state_mut["edfa_devices"][index] = replacement

        self.store.update(mutator)
        self.publish_event(
            "info",
            f"Applied EDFA template to {len(updated_devices)} device(s).",
            category="edfa",
        )
        self.notify_state_changed()

    def probe_psu_device(self, device_id: str):
        state = self.store.get_state()
        device = _find_in_collection(state["psu_devices"], device_id)
        try:
            with self._io_lock:
                client = self._get_psu_client(device)
                idn = client.idn()
                config_mode = client.config_get()
                ch1 = client.output_state(1).strip()
                ch2 = client.output_state(2).strip()

            self._update_psu_runtime(
                device_id,
                lambda target: target.update(
                    {
                        "connected": True,
                        "reachable": True,
                        "idn": idn,
                        "config_mode": config_mode,
                        "channel_states": {
                            "1": self._normalize_psu_state_text(ch1),
                            "2": self._normalize_psu_state_text(ch2),
                        },
                        "last_error": "",
                        "last_contact_at": _now_iso(),
                        "last_action": "Probe and state refresh completed",
                    }
                ),
            )
            self.publish_event("info", f"PSU device {device['name']} is reachable.", category="psu", device_id=device_id)
        except PsuCommunicationError as exc:
            self._update_psu_runtime(
                device_id,
                lambda target: target.update(
                    {
                        "connected": False,
                        "reachable": False,
                        "last_error": str(exc),
                        "last_contact_at": _now_iso(),
                        "last_action": "Probe failed",
                    }
                ),
            )
            self.publish_event("error", str(exc), category="psu", device_id=device_id)
            raise

    def disconnect_psu_device(self, device_id: str):
        self._close_psu_client(device_id)
        self._update_psu_runtime(
            device_id,
            lambda target: target.update(
                {
                    "connected": False,
                    "last_contact_at": _now_iso(),
                    "last_action": "Disconnected from PSU session",
                }
            ),
        )
        self.publish_event("info", f"Closed PSU session for {device_id}.", category="psu", device_id=device_id)

    def refresh_psu_device(self, device_id: str):
        state = self.store.get_state()
        device = _find_in_collection(state["psu_devices"], device_id)
        try:
            with self._io_lock:
                client = self._get_psu_client(device)
                ch1 = client.output_state(1).strip()
                ch2 = client.output_state(2).strip()
                config_mode = client.config_get()

            self._update_psu_runtime(
                device_id,
                lambda target: target.update(
                    {
                        "connected": True,
                        "reachable": True,
                        "config_mode": config_mode,
                        "channel_states": {
                            "1": self._normalize_psu_state_text(ch1),
                            "2": self._normalize_psu_state_text(ch2),
                        },
                        "last_error": "",
                        "last_contact_at": _now_iso(),
                        "last_action": "Channel states refreshed",
                    }
                ),
            )
            self.publish_event("info", f"Refreshed PSU outputs for {device['name']}.", category="psu", device_id=device_id)
        except PsuCommunicationError as exc:
            self._update_psu_runtime(
                device_id,
                lambda target: target.update(
                    {
                        "connected": False,
                        "reachable": False,
                        "last_error": str(exc),
                        "last_contact_at": _now_iso(),
                        "last_action": "Refresh failed",
                    }
                ),
            )
            self.publish_event("error", str(exc), category="psu", device_id=device_id)
            raise

    def set_psu_independent_mode(self, device_id: str):
        state = self.store.get_state()
        device = _find_in_collection(state["psu_devices"], device_id)
        try:
            with self._io_lock:
                client = self._get_psu_client(device)
                client.set_independent_mode()
                config_mode = client.config_get()
                ch1 = client.output_state(1).strip()
                ch2 = client.output_state(2).strip()

            self._update_psu_runtime(
                device_id,
                lambda target: target.update(
                    {
                        "connected": True,
                        "reachable": True,
                        "config_mode": config_mode,
                        "channel_states": {
                            "1": self._normalize_psu_state_text(ch1),
                            "2": self._normalize_psu_state_text(ch2),
                        },
                        "last_error": "",
                        "last_contact_at": _now_iso(),
                        "last_action": "Independent mode applied",
                    }
                ),
            )
            self.publish_event("info", f"Applied independent mode to {device['name']}.", category="psu", device_id=device_id)
        except PsuCommunicationError as exc:
            self._update_psu_runtime(
                device_id,
                lambda target: target.update(
                    {
                        "connected": False,
                        "reachable": False,
                        "last_error": str(exc),
                        "last_contact_at": _now_iso(),
                        "last_action": "Independent mode failed",
                    }
                ),
            )
            self.publish_event("error", str(exc), category="psu", device_id=device_id)
            raise

    def set_psu_channel_output(self, device_id: str, channel: int, turn_on: bool, source: str = "manual"):
        if channel not in (1, 2):
            raise ValueError("PSU channel must be 1 or 2.")
        state = self.store.get_state()
        device = _find_in_collection(state["psu_devices"], device_id)
        try:
            with self._io_lock:
                client = self._get_psu_client(device)
                if turn_on:
                    client.output_on(channel)
                else:
                    client.output_off(channel)
                state_text = client.output_state(channel).strip()
                config_mode = client.config_get()

            action_label = f"{source.title()} CH{channel} {'ON' if turn_on else 'OFF'}"
            self._update_psu_runtime(
                device_id,
                lambda target: self._mark_psu_channel_state(
                    target,
                    str(channel),
                    self._normalize_psu_state_text(state_text),
                    config_mode,
                    action_label,
                    "",
                    True,
                ),
            )
            self.publish_event(
                "info",
                f"{device['name']}: CH{channel} {'ON' if turn_on else 'OFF'} ({source}).",
                category="psu",
                device_id=device_id,
            )
        except PsuCommunicationError as exc:
            self._update_psu_runtime(
                device_id,
                lambda target: target.update(
                    {
                        "connected": False,
                        "reachable": False,
                        "last_error": str(exc),
                        "last_contact_at": _now_iso(),
                        "last_action": f"Failed to set CH{channel} {'ON' if turn_on else 'OFF'}",
                    }
                ),
            )
            self.publish_event("error", str(exc), category="psu", device_id=device_id)
            raise

    @staticmethod
    def _mark_psu_channel_state(target: dict, channel_key: str, state_text: str, config_mode: str, last_action: str, last_error: str, reachable: bool):
        target["connected"] = True
        target["reachable"] = reachable
        target["config_mode"] = config_mode
        target["channel_states"][channel_key] = state_text
        target["last_error"] = last_error
        target["last_contact_at"] = _now_iso()
        target["last_action"] = last_action

    @staticmethod
    def _normalize_psu_state_text(state_text: str) -> str:
        if state_text == "1":
            return "ON"
        if state_text == "0":
            return "OFF"
        return state_text or "unknown"
