"""B4: package staging must inject WSS only into the temporary copy."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/tv-app.py"


def test_monitor_packaging_stages_and_injects_without_modifying_source(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("webos_tv_app_build", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    source = ROOT / "apps/gway-monitor/app.js"
    original = source.read_bytes()
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"bridge_url": "wss://example.test:8769"}))
    output = tmp_path / "dist"

    def fake_command(tool, *args):
        assert tool == "ares-package"
        assert args[0] == "-o"
        stage_root = Path(args[1])
        staged = Path(args[2])
        staged_app = (staged / "app.js").read_text()
        assert "wss://example.test:8769" in staged_app
        assert (staged / "channel-registry.js").is_file()
        metadata = json.loads((staged / "appinfo.json").read_text())
        package = stage_root / f"{metadata['id']}_{metadata['version']}_all.ipk"
        package.write_bytes(b"test-package")
        return ""

    monkeypatch.setattr(module, "command", fake_command)
    monkeypatch.setattr(
        sys, "argv",
        ["tv-app.py", "gway-monitor", "--config", str(config), "--output-dir", str(output)],
    )
    assert module.main() == 0
    assert source.read_bytes() == original
    assert len(list(output.glob("*.ipk"))) == 1
