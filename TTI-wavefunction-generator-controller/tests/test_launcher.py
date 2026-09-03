import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import threading

import pytest


spec = importlib.util.spec_from_file_location("launcher", Path(__file__).parents[1] / "launcher.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.fixture
def http_peer():
    class Handler(BaseHTTPRequestHandler):
        payload = {}

        def do_GET(self):
            self.server.requests.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(self.payload).encode())

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, Handler
    server.shutdown()
    server.server_close()
    thread.join()


def test_existing_controller_is_reused_without_setup(http_peer, monkeypatch):
    server, handler = http_peer
    handler.payload = {"info": {"title": "TGF3162 Controller"},
                       "paths": {"/api/channels/{channel}/output": {}}}
    monkeypatch.setattr(launcher, "setup_environment", lambda *_: pytest.fail("Must not install into a running instance"))
    assert launcher.main(["--port", str(server.server_port), "--no-browser"]) == 0
    assert server.requests == ["/openapi.json"]  # No output/configuration mutation.


def test_other_service_is_not_reused_or_stopped(http_peer):
    server, handler = http_peer
    handler.payload = {"info": {"title": "Other service"}}
    with pytest.raises(launcher.LaunchError, match="another service"):
        launcher.main(["--port", str(server.server_port), "--no-browser"])
    assert launcher.server_status("127.0.0.1", server.server_port) == "occupied"
    handler.payload = ["unexpected", "json"]
    assert launcher.server_status("127.0.0.1", server.server_port) == "occupied"


def test_free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    assert launcher.server_status("127.0.0.1", port) == "free"


def test_incompatible_environment_is_preserved(tmp_path):
    env = tmp_path / "old environment"
    env.mkdir()
    sentinel = env / "keep.txt"
    sentinel.write_text("existing data")
    with pytest.raises(launcher.LaunchError, match="another OS"):
        launcher.setup_environment(env)
    assert sentinel.read_text() == "existing data"


def test_environment_marker_skips_network_and_tracks_project_changes(tmp_path, monkeypatch):
    root = tmp_path / "project with spaces"
    root.mkdir()
    project = root / "pyproject.toml"
    project.write_text("initial config")
    env = tmp_path / "venv"
    python = env / ("Scripts/python.exe" if launcher.os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    python.touch()
    monkeypatch.setattr(launcher, "ROOT", root)
    monkeypatch.setattr(launcher, "runtime_info", lambda _: {"python": [3, 12, 0], "prefix": str(env)})
    installs = []
    monkeypatch.setattr(launcher, "run", lambda command, _: installs.append(command))
    launcher.setup_environment(env)
    launcher.setup_environment(env)
    assert len(installs) == 1
    project.write_text("changed dependency configuration")
    launcher.setup_environment(env)
    assert len(installs) == 2


def test_launcher_lock_blocks_duplicate_setup_and_releases(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    with launcher.LauncherLock():
        with pytest.raises(launcher.LaunchError, match="Another launcher"):
            with launcher.LauncherLock():
                pass
    with launcher.LauncherLock():
        pass


@pytest.mark.parametrize("value", ["0", "65536", "not-a-number"])
def test_invalid_ports(value):
    with pytest.raises(SystemExit):
        launcher.main(["--port", value])


def test_wildcard_browser_urls():
    assert launcher.base_url("0.0.0.0", 8000) == "http://127.0.0.1:8000"
    assert launcher.base_url("::", 8000) == "http://[::1]:8000"


def test_network_defaults():
    assert launcher.DEFAULT_HOST == "0.0.0.0"
    assert launcher.DEFAULT_PORT == 8005
    assert launcher.base_url(launcher.DEFAULT_HOST, launcher.DEFAULT_PORT) == "http://127.0.0.1:8005"
