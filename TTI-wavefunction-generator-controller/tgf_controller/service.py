"""One serialized owner of the instrument, shared by all HTTP clients."""

import copy
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from .models import ChannelSettings, ConnectionSettings
from .transport import InstrumentError, LanTransport


def default_config_path() -> Path:
    if os.environ.get("TGF_CONFIG_PATH"):
        return Path(os.environ["TGF_CONFIG_PATH"])
    root = Path(os.environ.get("APPDATA", Path.home() / ".config"))
    return root / "tgf3162-controller" / "connection.json"


def stamp():
    return datetime.now(timezone.utc).isoformat()


class Controller:
    def __init__(self, config_path=None, transport_factory=LanTransport):
        self.lock = threading.RLock()
        self.path = Path(config_path) if config_path else default_config_path()
        self.presets_path = self.path.with_name(f"{self.path.stem}.channels.json")
        self.transport_factory = transport_factory
        self.transport = None
        self.config = ConnectionSettings()
        self.config_warning = None
        if self.path.exists():
            try:
                self.config = ConnectionSettings.model_validate_json(self.path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                self.config_warning = "Saved connection settings could not be read. Demo defaults are in use."
        self.connected = self.config.mode == "demo"
        self.identity = "Aim-TTi,TGF3162,DEMO,simulated" if self.connected else None
        self.last_error = None
        self.last_refreshed_at = None
        self.events = []
        self.saved_settings = [None, None]
        if self.presets_path.exists():
            try:
                saved = json.loads(self.presets_path.read_text(encoding="utf-8"))
                if not isinstance(saved, list) or len(saved) != 2:
                    raise ValueError("Expected two channels")
                self.saved_settings = [
                    ChannelSettings.model_validate(item).model_dump(mode="json") if item is not None else None
                    for item in saved
                ]
            except (ValueError, OSError, json.JSONDecodeError):
                self.config_warning = "Saved channel settings could not be read and were ignored."
        self.channels = self._channels(self.connected)

    def _channels(self, demo=False):
        return [{"channel": c, "settings": ChannelSettings().normalized() if demo else None,
                 "output_enabled": False if demo else None, "updated_at": None,
                 "source": "simulation" if demo else "unknown"} for c in (1, 2)]

    def _event(self, message, kind="info"):
        self.events.insert(0, {"time": stamp(), "kind": kind, "message": message})
        del self.events[40:]

    def _save_channel_settings(self, channel, settings):
        self.saved_settings[channel - 1] = settings.model_dump(mode="json")
        try:
            self.presets_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.presets_path.with_suffix(".tmp")
            temp.write_text(json.dumps(self.saved_settings, indent=2), encoding="utf-8")
            temp.replace(self.presets_path)
        except OSError:
            self._event("Settings were applied but could not be saved for the next launch.", "warning")

    def state(self):
        with self.lock:
            return copy.deepcopy({"connected": self.connected, "mode": self.config.mode,
                "connection": self.config.model_dump(mode="json"), "identity": self.identity,
                "channels": self.channels, "saved_settings": self.saved_settings, "events": self.events,
                "last_error": self.last_error, "config_warning": self.config_warning,
                "last_refreshed_at": self.last_refreshed_at,
                "hardware_readback_available": self.config.mode == "demo",
                "state_notice": "Simulation" if self.config.mode == "demo" else
                "Last accepted commands only. Front-panel changes and actual output are not read back."})

    def save(self, settings):
        with self.lock:
            if self.connected and settings != self.config:
                raise InstrumentError("Disconnect before changing the connection settings.", 409)
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temp = self.path.with_suffix(".tmp")
                temp.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
                temp.replace(self.path)
            except OSError as exc:
                raise InstrumentError("Could not save connection settings. Check the configuration directory permissions.", 500) from exc
            self.config = settings
            self.config_warning = None
            self._event("Connection settings saved.")
            return self.state()

    @staticmethod
    def _identify(transport):
        identity = transport.query("*IDN?")
        fields = identity.split(",")
        if len(fields) < 2 or fields[1].strip().upper() != "TGF3162":
            raise InstrumentError(f"Expected a TGF3162; received identity: {identity[:160]}", 409)
        return identity

    def test(self, settings):
        with self.lock:
            if settings.mode == "demo":
                return {"ok": True, "identity": "Aim-TTi,TGF3162,DEMO,simulated", "mode": "demo"}
            if self.connected and self.config.mode == "lan" and settings == self.config:
                try:
                    identity = self._identify(self.transport)
                except InstrumentError as exc:
                    self._fail(exc)
                    raise
            else:
                transport = self.transport_factory(settings)
                try:
                    transport.connect()
                    identity = self._identify(transport)
                finally:
                    transport.close()
            return {"ok": True, "identity": identity, "mode": "lan"}

    def connect(self):
        with self.lock:
            if self.connected:
                return self.state()
            if self.config.mode == "demo":
                self.channels = self._channels(True)
                self.identity = "Aim-TTi,TGF3162,DEMO,simulated"
            else:
                self.transport = self.transport_factory(self.config)
                try:
                    self.transport.connect()
                    self.identity = self._identify(self.transport)
                except InstrumentError as exc:
                    self._fail(exc)
                    raise
                self.channels = self._channels()
            self.connected = True
            self.last_error = None
            self._event("Demo session started." if self.config.mode == "demo" else "Instrument connected. Output state is unknown.")
            return self.state()

    def disconnect(self):
        with self.lock:
            if self.transport:
                self.transport.close()
            self.transport = None
            self.connected = False
            self.identity = None
            self.last_refreshed_at = None
            self.channels = self._channels()
            self._event("Disconnected. Hardware outputs were not changed.")
            return self.state()

    def _fail(self, exc):
        if self.transport:
            self.transport.close()
        self.transport = None
        self.connected = False
        self.last_refreshed_at = None
        self.channels = self._channels()
        self.last_error = str(exc)
        self._event(str(exc), "error")

    def _require_connection(self):
        if not self.connected:
            raise InstrumentError("Connect to the instrument or start Demo Mode first.", 409)

    def _registers(self):
        try:
            return {name: int(self.transport.query(name + "?")) for name in ("EER", "QER", "*ESR")}
        except ValueError as exc:
            raise InstrumentError("Invalid instrument status-register reply.") from exc

    def _check(self, command):
        registers = self._registers()
        if registers["EER"] or registers["QER"] or registers["*ESR"] & 0x34:
            raise InstrumentError(f"Instrument rejected {command}: EER={registers['EER']}, QER={registers['QER']}, ESR={registers['*ESR']}. Some settings may have changed; reconnect and reapply.")

    def _execute(self, commands, allow_power_on=False):
        if self.config.mode == "demo":
            return
        try:
            # Fire-and-forget fast path. Some TGF3162 firmware executes these
            # commands but does not return *OPC? reliably over the raw socket.
            # Queries and status checks are reserved for explicit refresh.
            self.transport.write(";".join(commands))
        except InstrumentError as exc:
            self._fail(exc)
            raise

    def apply(self, channel, settings):
        with self.lock:
            self._require_connection()
            values = settings.normalized()
            mod = values["modulation"]
            # No OUTPUT ON/OFF here: applying settings never enables an output.
            commands = [f"CHN {channel}", "MOD OFF", "SWP OFF", "BST OFF",
                "AMPLRNG AUTO", "DCOFFS 0", "ZLOAD 50", "WAVE SINE"]
            commands += ["OUTPUT NORMAL", "MODFMDEV 0", f"FREQ {values['frequency_hz']:.6f}",
                f"AMPL {values['amplitude_vpp']:.12g}", f"PHASE {values['phase_deg']:.3f}"]
            if mod["mode"] != "off":
                prefix = "MODAM" if mod["mode"] == "am" else "MODFM"
                commands += [f"{prefix}SRC INT", f"{prefix}SHAPE SINE", f"{prefix}FREQ {mod['frequency_hz']:.6f}"]
                commands += [f"MODAMDEPTH {mod['depth_percent']:.2f}"] if mod["mode"] == "am" else [f"MODFMDEV {mod['deviation_hz']:.6f}"]
                commands.append(f"MOD {mod['mode'].upper()}")
            self._execute(commands, allow_power_on=True)
            current = self.channels[channel - 1]
            current.update(settings=values, source="simulation" if self.config.mode == "demo" else "commanded", updated_at=stamp())
            self._save_channel_settings(channel, settings)
            self._event(f"CH{channel} settings {'simulated' if self.config.mode == 'demo' else 'accepted'}: {values['frequency_hz']:g} Hz, {values['amplitude_vpp']:.6g} Vpp, {mod['mode'].upper()}.")
            return self.state()

    def output(self, channel, enabled):
        with self.lock:
            self._require_connection()
            if enabled and self.channels[channel - 1]["settings"] is None:
                raise InstrumentError("Apply this channel's settings before enabling its output.", 409)
            # Explicit OFF remains available when no channel settings are known.
            commands = [f"CHN {channel}", f"OUTPUT {'ON' if enabled else 'OFF'}"]
            self._execute(commands, allow_power_on=not enabled)
            self.channels[channel - 1].update(output_enabled=enabled, updated_at=stamp())
            self._event(f"CH{channel} output {'ON' if enabled else 'OFF'} {'simulated' if self.config.mode == 'demo' else 'command accepted'}.")
            return self.state()

    def refresh(self):
        with self.lock:
            self._require_connection()
            if self.config.mode == "lan":
                try:
                    self.identity = self._identify(self.transport)
                    registers = self._registers()
                    if registers["*ESR"] & 128:
                        self.channels = self._channels()
                        self._event("Power-on flag detected. Cached channel settings invalidated.", "warning")
                    if registers["EER"] or registers["QER"] or registers["*ESR"] & 0x34:
                        raise InstrumentError(f"Instrument reports {registers}. State is unknown.")
                except InstrumentError as exc:
                    self._fail(exc)
                    raise
            self.last_refreshed_at = stamp()
            self._event("Device status refreshed. This model cannot read back individual channel values.")
            return self.state()
