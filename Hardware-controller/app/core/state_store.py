import json
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import config
from app.core.security import build_password_record


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _normalize_weekdays(days, default):
    if not isinstance(days, list):
        return list(default)
    normalized = []
    for value in days:
        try:
            day = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= day <= 6 and day not in normalized:
            normalized.append(day)
    return normalized or list(default)


def _default_edfa_channels():
    return [
        {
            "key": key,
            "label": key.upper(),
            "power": power,
            "assumed_on": False,
        }
        for key, power in config.EDFA_DEFAULT_POWERS.items()
    ]


def _default_edfa_schedule():
    return {
        "enabled": False,
        "days": list(config.DEFAULT_WEEKDAYS),
        "on_time": "08:00",
        "off_time": "18:00",
    }


def _default_psu_channel_schedule():
    return {
        "enabled": False,
        "days": list(config.DEFAULT_WEEKDAYS),
        "on_time": "",
        "off_time": "",
    }


def _default_laser_lock_system():
    return {
        "name": "MIGA2 Laser Lock",
        "ip": "",
        "port": config.LASER_LOCK_DEFAULT_PORT,
        "timeout_sec": config.NETWORK_TIMEOUT_SEC,
        "notes": "",
    }


def _normalize_edfa_device(device: dict, index: int) -> dict:
    device_type = str(device.get("device_type") or "network_edfa").strip()
    normalized = {
        "id": str(device.get("id") or uuid4().hex[:8]),
        "device_type": device_type if device_type in {"network_edfa", "bragg_cefa"} else "network_edfa",
        "name": str(device.get("name") or f"EDFA System {index}").strip() or f"EDFA System {index}",
        "ip": str(device.get("ip") or "").strip(),
        "serial_port": str(device.get("serial_port") or "").strip(),
        "apc_setpoint_dbm": float(device.get("apc_setpoint_dbm", 33.0)),
        "port": int(device.get("port") or config.EDFA_DEFAULT_PORT),
        "timeout_sec": float(device.get("timeout_sec") or config.NETWORK_TIMEOUT_SEC),
        "command_delay_sec": float(device.get("command_delay_sec") or config.EDFA_COMMAND_DELAY_SEC),
        "channels": _default_edfa_channels(),
        "schedule": _default_edfa_schedule(),
        "notes": str(device.get("notes") or "").strip(),
        "reachable": device.get("reachable"),
        "last_action": str(device.get("last_action") or "No action yet"),
        "last_error": str(device.get("last_error") or ""),
        "last_contact_at": str(device.get("last_contact_at") or ""),
    }

    if normalized["device_type"] == "bragg_cefa":
        normalized.update(
            {
                "connected": False,
                "serial_number": str(device.get("serial_number") or ""),
                "input_power": device.get("input_power") if isinstance(device.get("input_power"), dict) else {},
                "output_power": device.get("output_power") if isinstance(device.get("output_power"), dict) else {},
                "output_mode": str(device.get("output_mode") or ""),
                "output_state": str(device.get("output_state") or "UNKNOWN"),
            }
        )

    incoming_channels = device.get("channels") if isinstance(device.get("channels"), list) else []
    incoming_map = {str(item.get("key") or ""): item for item in incoming_channels if isinstance(item, dict)}
    for channel in normalized["channels"]:
        source = incoming_map.get(channel["key"], {})
        channel["label"] = str(source.get("label") or channel["label"]).strip() or channel["label"]
        channel["power"] = str(source.get("power") or channel["power"]).strip() or channel["power"]
        channel["assumed_on"] = bool(source.get("assumed_on", channel["assumed_on"]))

    source_schedule = device.get("schedule") if isinstance(device.get("schedule"), dict) else {}
    normalized["schedule"] = {
        "enabled": bool(source_schedule.get("enabled", normalized["schedule"]["enabled"])),
        "days": _normalize_weekdays(source_schedule.get("days"), config.DEFAULT_WEEKDAYS),
        "on_time": str(source_schedule.get("on_time") or normalized["schedule"]["on_time"]).strip(),
        "off_time": str(source_schedule.get("off_time") or normalized["schedule"]["off_time"]).strip(),
    }
    return normalized


def _normalize_psu_device(device: dict, index: int) -> dict:
    normalized = {
        "id": str(device.get("id") or uuid4().hex[:8]),
        "name": str(device.get("name") or f"PSU System {index}").strip() or f"PSU System {index}",
        "ip": str(device.get("ip") or "").strip(),
        "port": int(device.get("port") or config.PSU_DEFAULT_PORT),
        "timeout_sec": float(device.get("timeout_sec") or config.NETWORK_TIMEOUT_SEC),
        "schedule": {
            "channels": {
                "1": _default_psu_channel_schedule(),
                "2": _default_psu_channel_schedule(),
            }
        },
        "notes": str(device.get("notes") or "").strip(),
        "connected": bool(device.get("connected", False)),
        "reachable": device.get("reachable"),
        "idn": str(device.get("idn") or ""),
        "config_mode": str(device.get("config_mode") or ""),
        "channel_states": {
            "1": str((device.get("channel_states") or {}).get("1") or "unknown"),
            "2": str((device.get("channel_states") or {}).get("2") or "unknown"),
        },
        "last_action": str(device.get("last_action") or "No action yet"),
        "last_error": str(device.get("last_error") or ""),
        "last_contact_at": str(device.get("last_contact_at") or ""),
    }

    source_schedule = device.get("schedule") if isinstance(device.get("schedule"), dict) else {}
    source_channels = source_schedule.get("channels") if isinstance(source_schedule.get("channels"), dict) else {}
    for channel_key in config.PSU_CHANNELS:
        incoming = source_channels.get(channel_key) if isinstance(source_channels.get(channel_key), dict) else {}
        normalized["schedule"]["channels"][channel_key] = {
            "enabled": bool(incoming.get("enabled", False)),
            "days": _normalize_weekdays(incoming.get("days"), config.DEFAULT_WEEKDAYS),
            "on_time": str(incoming.get("on_time") or "").strip(),
            "off_time": str(incoming.get("off_time") or "").strip(),
        }
    return normalized


def _default_state() -> dict:
    now = _now_iso()
    return {
        "schema_version": 1,
        "server": {
            "default_host": config.DEFAULT_HOST,
            "default_port": config.DEFAULT_PORT,
        },
        "auth": build_password_record(config.DEFAULT_PASSWORD),
        "edfa_devices": [],
        "psu_devices": [],
        "laser_lock_system": _default_laser_lock_system(),
        "metadata": {
            "created_at": now,
            "updated_at": now,
        },
    }


def _normalize_state(state: dict) -> dict:
    defaults = _default_state()
    normalized = {
        "schema_version": int(state.get("schema_version") or defaults["schema_version"]),
        "server": {
            "default_host": str((state.get("server") or {}).get("default_host") or defaults["server"]["default_host"]),
            "default_port": int((state.get("server") or {}).get("default_port") or defaults["server"]["default_port"]),
        },
        "auth": state.get("auth") if isinstance(state.get("auth"), dict) else defaults["auth"],
        "edfa_devices": [],
        "psu_devices": [],
        "laser_lock_system": _default_laser_lock_system(),
        "metadata": {
            "created_at": str((state.get("metadata") or {}).get("created_at") or defaults["metadata"]["created_at"]),
            "updated_at": str((state.get("metadata") or {}).get("updated_at") or defaults["metadata"]["updated_at"]),
        },
    }

    raw_edfa = state.get("edfa_devices") if isinstance(state.get("edfa_devices"), list) else []
    raw_psu = state.get("psu_devices") if isinstance(state.get("psu_devices"), list) else []
    normalized["edfa_devices"] = [_normalize_edfa_device(item, index + 1) for index, item in enumerate(raw_edfa)]
    normalized["psu_devices"] = [_normalize_psu_device(item, index + 1) for index, item in enumerate(raw_psu)]

    raw_laser = state.get("laser_lock_system") if isinstance(state.get("laser_lock_system"), dict) else {}
    normalized["laser_lock_system"] = {
        "name": str(raw_laser.get("name") or "MIGA2 Laser Lock").strip() or "MIGA2 Laser Lock",
        "ip": str(raw_laser.get("ip") or "").strip(),
        "port": int(raw_laser.get("port") or config.LASER_LOCK_DEFAULT_PORT),
        "timeout_sec": float(raw_laser.get("timeout_sec") or config.NETWORK_TIMEOUT_SEC),
        "notes": str(raw_laser.get("notes") or "").strip(),
    }

    auth = normalized["auth"]
    if not auth.get("salt") or not auth.get("hash"):
        normalized["auth"] = defaults["auth"]
    return normalized


class StateStore:
    def __init__(self, state_path: Path | None = None):
        self.state_path = state_path or config.STATE_FILE_PATH
        self._lock = threading.RLock()
        self._state = self._load()

    def _load(self) -> dict:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            state = _default_state()
            self._write(state)
            return state

        try:
            with open(self.state_path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except Exception:
            raw = _default_state()

        normalized = _normalize_state(raw if isinstance(raw, dict) else {})
        self._write(normalized)
        return normalized

    def _write(self, state: dict):
        with open(self.state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)

    def get_state(self) -> dict:
        with self._lock:
            return deepcopy(self._state)

    def update(self, mutator):
        with self._lock:
            state = deepcopy(self._state)
            mutator(state)
            state["metadata"]["updated_at"] = _now_iso()
            self._write(state)
            self._state = state
            return deepcopy(state)

    def replace_auth_record(self, record: dict):
        def mutator(state: dict):
            state["auth"] = record

        self.update(mutator)

    def next_device_name(self, family: str) -> str:
        state = self.get_state()
        if family == "edfa":
            count = len(state["edfa_devices"]) + 1
            return f"EDFA System {count}"
        count = len(state["psu_devices"]) + 1
        return f"PSU System {count}"
