import json
import math
import socketserver
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tgf_controller.app import create_app
from tgf_controller.models import ChannelSettings, ConnectionSettings, amplitude_vpp
from tgf_controller.service import Controller


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Controller(tmp_path / "settings.json"))) as c:
        yield c


def test_demo_independent_channels_and_outputs(client):
    assert client.get("/").status_code == 200
    result = client.put("/api/channels/1/settings", json={"frequency_hz": 2e6, "phase_deg": -90,
        "modulation": {"mode": "am", "frequency_hz": 800, "depth_percent": 75}})
    assert result.status_code == 200
    state = result.json()
    assert state["channels"][0]["settings"]["frequency_hz"] == 2e6
    assert state["channels"][0]["output_enabled"] is False
    assert state["channels"][1]["settings"]["frequency_hz"] == 10000
    state = client.put("/api/channels/1/output", json={"enabled": True}).json()
    assert state["channels"][0]["output_enabled"] is True
    assert state["channels"][1]["output_enabled"] is False
    result = client.put("/api/channels/1/settings", json={"frequency_hz": 1e6})
    assert result.json()["channels"][0]["output_enabled"] is True


@pytest.mark.parametrize("payload", [
    {"frequency_hz": 160000001}, {"frequency_hz": 0}, {"frequency_hz": 1e8, "amplitude": 6},
    {"frequency_hz": 160e6, "amplitude": 3}, {"phase_deg": 361},
    {"amplitude": 0}, {"amplitude": 30, "amplitude_unit": "dBm"},
    {"frequency_hz": 51e6, "modulation": {"mode": "am"}},
    {"frequency_hz": 1e3, "modulation": {"mode": "fm", "deviation_hz": 1001}},
    {"frequency_hz": 159e6, "modulation": {"mode": "fm", "deviation_hz": 2e6}},
    {"frequency_hz": 49e6, "amplitude": 8, "modulation": {"mode": "fm", "deviation_hz": 2e6}},
    {"modulation": {"mode": "am", "depth_percent": 101}},
    {"modulation": {"mode": "fm", "frequency_hz": 10e6 + 1}},
    {"frequency_hz": "nan"}, {"unknown": 1},
])
def test_invalid_settings_do_not_change_state(client, payload):
    before = client.get("/api/state").json()["channels"]
    assert client.put("/api/channels/1/settings", json=payload).status_code == 422
    assert client.get("/api/state").json()["channels"] == before


def test_units_and_boundaries():
    assert amplitude_vpp(1 / math.sqrt(8), "Vrms") == pytest.approx(1)
    assert amplitude_vpp(0, "dBm") == pytest.approx(math.sqrt(.4))
    for frequency, amplitude in [(50e6, 10), (100e6, 5), (160e6, 2.5)]:
        ChannelSettings(frequency_hz=frequency, amplitude=amplitude)
    ChannelSettings(frequency_hz=80e6, modulation={"mode": "fm", "deviation_hz": 80e6})
    assert ChannelSettings(phase_deg=.0015).normalized()["phase_deg"] == .002
    with pytest.raises(ValidationError):
        ChannelSettings(amplitude=float("inf"))


def test_config_persistence_and_invalid_channel(client, tmp_path):
    assert client.put("/api/channels/3/output", json={"enabled": False}).status_code == 422
    assert client.put("/api/channels/1/output", json={"enabled": "false"}).status_code == 422
    assert client.put("/api/connection", json={"mode": "lan"}).status_code == 409
    client.post("/api/disconnect")
    assert client.put("/api/channels/1/output", json={"enabled": True}).status_code == 409
    settings = {"mode": "lan", "host": "192.168.5.22", "port": 9221, "timeout_s": 1}
    assert client.put("/api/connection", json=settings).status_code == 200
    new = Controller(tmp_path / "settings.json")
    assert str(new.config.host) == "192.168.5.22"
    assert new.connected is False  # Never reconnect hardware automatically on startup.
    assert new.channels[0]["output_enabled"] is None


class Device:
    """A TCP peer exercising framing and transactions, not a hardware substitute."""
    def __init__(self):
        self.commands = []
        self.identity = "THURLBY THANDAR,TGF3162,123456,1.03"
        self.channel = 1
        self.frequency = {1: None, 2: None}
        self.outputs = {1: False, 2: False}
        self.reject = None
        self.error = 0
        self.esr = 0
        self.drop_on = None

    def response(self, line):
        self.commands.append(line)
        if line == self.drop_on:
            return "CLOSE"
        if line == self.reject:
            self.error, self.esr = -36, 16
        if line == "*IDN?": return self.identity
        if line == "EER?":
            result, self.error = self.error, 0
            return str(result)
        if line == "QER?": return "0"
        if line == "*ESR?":
            result, self.esr = self.esr, 0
            return str(result)
        if line == "*OPC?": return "1"
        if line.startswith("CHN "): self.channel = int(line.split()[1])
        if line.startswith("FREQ "): self.frequency[self.channel] = float(line.split()[1])
        if line in ("OUTPUT ON", "OUTPUT OFF"): self.outputs[self.channel] = line.endswith("ON")
        return None


@pytest.fixture
def lan(tmp_path):
    device = Device()

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            for raw in self.rfile:
                response = device.response(raw.decode("ascii").strip())
                if response == "CLOSE": return
                if response is not None:
                    # Deliberately fragment a CRLF-terminated response.
                    data = (response + "\r\n").encode()
                    try:
                        self.wfile.write(data[:2]); self.wfile.flush()
                        self.wfile.write(data[2:]); self.wfile.flush()
                    except OSError:
                        return

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    controller = Controller(tmp_path / "lan.json")
    controller.disconnect()
    controller.save(ConnectionSettings(mode="lan", host="127.0.0.1", port=server.server_address[1], timeout_s=.5))
    with TestClient(create_app(controller)) as client:
        yield client, controller, device
    server.shutdown(); server.server_close(); thread.join()


def test_lan_identity_only_connect_and_units(lan):
    client, controller, device = lan
    assert client.post("/api/connect").status_code == 200
    assert device.commands == ["*IDN?"]
    assert client.get("/api/state").json()["channels"][0]["settings"] is None
    assert client.put("/api/channels/1/output", json={"enabled": True}).status_code == 409
    result = client.put("/api/channels/2/settings", json={"frequency_hz": 1e6, "amplitude": 0,
        "amplitude_unit": "dBm", "phase_deg": 90,
        "modulation": {"mode": "fm", "frequency_hz": 3000, "deviation_hz": 5000}})
    assert result.status_code == 200, result.text
    assert "MODFMSRC INT" in device.commands
    assert "MODFMSHAPE SINE" in device.commands
    assert "MODFMFREQ 3000.000000" in device.commands
    assert "MODFMDEV 5000.000000" in device.commands
    assert "PHASE 90.000" in device.commands
    assert "CHN2CONFIG MAINOUT" in device.commands
    assert not any(c in ("OUTPUT ON", "OUTPUT OFF", "*RST", "ALIGN", "FREQ?") for c in device.commands)
    assert device.frequency == {1: None, 2: 1e6}
    assert result.json()["channels"][1]["source"] == "commanded"
    assert result.json()["channels"][1]["settings"]["amplitude_vpp"] == pytest.approx(math.sqrt(.4))
    client.put("/api/channels/2/output", json={"enabled": True})
    assert device.outputs == {1: False, 2: True}
    client.post("/api/disconnect")
    assert device.outputs[2] is True


def test_wrong_device_rejected(lan):
    client, _, device = lan
    device.identity = "Other,TGF3082,123,1"
    assert client.post("/api/connect").status_code == 409
    assert not client.get("/api/state").json()["connected"]
    assert device.commands == ["*IDN?"]


def test_partial_failure_invalidates_cache_and_stops_writes(lan):
    client, _, device = lan
    client.post("/api/connect")
    device.reject = "FREQ 12000.000000"
    result = client.put("/api/channels/1/settings", json={"frequency_hz": 12000})
    assert result.status_code == 502
    assert "EER=-36" in result.json()["detail"]
    assert not client.get("/api/state").json()["connected"]
    assert client.get("/api/state").json()["channels"][0]["settings"] is None
    assert "PHASE 0.000" not in device.commands


def test_disconnect_mid_query(lan):
    client, _, device = lan
    client.post("/api/connect")
    device.drop_on = "EER?"
    assert client.put("/api/channels/1/output", json={"enabled": False}).status_code == 503
    assert not client.get("/api/state").json()["connected"]
    assert "OUTPUT OFF" not in device.commands


def test_concurrent_channel_transactions_do_not_interleave(lan):
    client, controller, device = lan
    client.post("/api/connect")
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(controller.apply, 1, ChannelSettings(frequency_hz=12345))
        b = pool.submit(controller.apply, 2, ChannelSettings(frequency_hz=67890))
        a.result(); b.result()
    assert device.frequency == {1: 12345, 2: 67890}
    first, second = [i for i, cmd in enumerate(device.commands) if cmd.startswith("CHN ")]
    assert "*OPC?" in device.commands[first:second]


def test_power_cycle_cannot_enable_unconfigured_output(lan):
    client, _, device = lan
    client.post("/api/connect")
    assert client.put("/api/channels/1/settings", json={}).status_code == 200
    device.esr = 128
    result = client.put("/api/channels/1/output", json={"enabled": True})
    assert result.status_code == 409
    assert "OUTPUT ON" not in device.commands


def test_unknown_output_can_be_disabled_after_power_on(lan):
    client, _, device = lan
    client.post("/api/connect")
    device.esr = 128
    result = client.put("/api/channels/1/output", json={"enabled": False})
    assert result.status_code == 200
    assert "OUTPUT OFF" in device.commands
    assert result.json()["channels"][0]["settings"] is None
