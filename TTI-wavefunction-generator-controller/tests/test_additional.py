from fastapi.testclient import TestClient

from tgf_controller.app import create_app
from tgf_controller.models import ConnectionSettings
from tgf_controller.service import Controller


def test_corrupt_config_is_explicit(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("not json")
    controller = Controller(path)
    assert controller.state()["config_warning"]
    assert controller.config.mode == "demo"


def test_identity_test_does_not_save_or_switch_modes(tmp_path):
    controller = Controller(tmp_path / "settings.json")
    before = controller.state()
    assert controller.test(ConnectionSettings())["ok"]
    assert controller.state() == before
    assert not controller.path.exists()


def test_demo_api_schema_and_assets(tmp_path):
    with TestClient(create_app(Controller(tmp_path / "settings.json"))) as client:
        schema = client.get("/openapi.json").json()
        assert "/api/channels/{channel}/output" in schema["paths"]
        for path in ("/static/styles.css", "/static/app.js", "/docs"):
            assert client.get(path).status_code == 200
