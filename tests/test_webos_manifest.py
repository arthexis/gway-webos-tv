"""D1-D4: manifest discovery, staging, safety and CLI compatibility."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tv_app_manifest", ROOT / "scripts/tv-app.py")
tv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tv)


def make_app(root, name, bridge="none", entry="index.html"):
    app = root / name
    app.mkdir()
    (app / "index.html").write_text("<html></html>")
    (app / "appinfo.json").write_text(json.dumps({
        "id": f"com.example.{name.replace('-', '')}", "version": "1.0.0", "main": entry,
    }))
    if bridge == "inject":
        (app / "app.js").write_text(tv.INJECTION_POINT)
    (app / "manifest.json").write_text(json.dumps({
        "schema": tv.MANIFEST_SCHEMA, "entry": entry,
        "bridge": {"mode": "none"} if bridge == "none" else
                  {"mode": "inject", "file": "app.js", "config_key": "bridge_url"},
    }))
    return app


def test_existing_apps_have_valid_manifests():
    assert tv.discover_apps() == ["connect-four", "gway-monitor", "remote-test"]
    for name in tv.discover_apps():
        manifest, meta = tv.load_manifest(ROOT / "apps" / name)
        assert manifest["bridge"]["mode"] == ("none" if name == "connect-four" else "inject")
        assert meta["main"] == "index.html"


def test_third_app_discovered_and_staged_without_config(tmp_path):
    apps = tmp_path / "apps"
    apps.mkdir()
    third = make_app(apps, "third")
    assert tv.discover_apps(apps) == ["third"]
    manifest, _ = tv.load_manifest(third)
    staged = tmp_path / "staged"
    tv.stage_app(third, staged, manifest, tmp_path / "absent-config.json")
    assert (staged / "index.html").is_file()
    assert not (staged / "manifest.json").exists()


def test_existing_wss_injection_preserves_source(tmp_path):
    source = ROOT / "apps/gway-monitor"
    manifest, _ = tv.load_manifest(source)
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"bridge_url": "wss://bridge.example.test:8769"}))
    original = (source / "app.js").read_bytes()
    staged = tmp_path / "staged"
    tv.stage_app(source, staged, manifest, config)
    assert "wss://bridge.example.test:8769" in (staged / "app.js").read_text()
    assert (source / "app.js").read_bytes() == original
    assert not (staged / "manifest.json").exists()
    assert (staged / "channels/hardware.js").is_file()


@pytest.mark.parametrize("path", ["../escape", "/etc/passwd", "x/../y", "x\\y", "", "./app.js"])
def test_unsafe_manifest_paths_rejected(path):
    with pytest.raises(ValueError):
        tv.safe_relative_path(path)


def test_invalid_manifests_and_symlinks_rejected(tmp_path):
    apps = tmp_path / "apps"
    apps.mkdir()
    app = make_app(apps, "third")
    manifest_path = app / "manifest.json"
    data = json.loads(manifest_path.read_text())
    data["unexpected"] = True
    manifest_path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        tv.load_manifest(app)
    del data["unexpected"]
    data["bridge"] = {"mode": "inject", "file": "../escape", "config_key": "bridge_url"}
    manifest_path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        tv.load_manifest(app)
    data["bridge"] = {"mode": "none"}
    manifest_path.write_text(json.dumps(data))
    (app / "escape").symlink_to(tmp_path)
    with pytest.raises(ValueError):
        tv.load_manifest(app)


def test_cli_all_packages_both_apps(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"bridge_url": "wss://bridge.example.test"}))
    out = tmp_path / "packages"
    calls = []

    def fake_command(tool, *args):
        assert tool == "ares-package"
        root, staged = Path(args[1]), Path(args[2])
        assert not (staged / "manifest.json").exists()
        if (staged / "app.js").is_file():
            assert "wss://bridge.example.test" in (staged / "app.js").read_text()
        else:
            assert (staged / "game.js").is_file()
        meta = json.loads((staged / "appinfo.json").read_text())
        (root / f"{meta['id']}_{meta['version']}_all.ipk").write_bytes(b"test-ipk")
        calls.append(meta["id"])
        return ""

    monkeypatch.setattr(tv, "command", fake_command)
    monkeypatch.setattr(sys, "argv", [
        "tv-app.py", "all", "--config", str(config), "--output-dir", str(out),
    ])
    assert tv.main() == 0
    assert len(calls) == 3
    assert len(list(out.glob("*.ipk"))) == 3
    assert set(calls) == {"com.arthexis.gway.connectfour", "com.arthexis.gway.monitor", "com.arthexis.gway.remotetest"}


def test_cli_rejects_duplicate_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "tv-app.py", "remote-test", "remote-test", "--output-dir", str(tmp_path),
    ])
    assert tv.main() == 1
