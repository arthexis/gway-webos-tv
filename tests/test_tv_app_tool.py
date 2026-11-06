import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "tv_app_tool", Path(__file__).parents[1] / "scripts/tv-app.py"
)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.test",
        "wss://user:pass@example.test",
        "wss://example.test/?token=secret",
        "wss://example.test/#fragment",
        "wss://example.test:bad",
    ],
)
def test_bridge_endpoint_rejects_unprotected_or_secret_bearing_urls(tmp_path, url):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"bridge_url": url}))
    with pytest.raises(ValueError):
        tool.endpoint_from_config(path)


def test_device_profile_mismatch_fails_before_network(tmp_path, monkeypatch):
    device_file = tmp_path / ".webos/tv/novacom-devices.json"
    device_file.parent.mkdir(parents=True)
    device_file.write_text(json.dumps([{"name": "lab-tv", "host": "192.0.2.4"}]))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(tool, "tv_status", lambda host: pytest.fail("network must not be called"))
    with pytest.raises(ValueError, match="profile address"):
        tool.verify_device("lab-tv", "192.0.2.5")
