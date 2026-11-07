"""CI webOS TV auto-deploy: offline is optional, unsafe/failed install is not."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("auto_tv_deploy", ROOT / "scripts/auto-tv-deploy.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def home_with_profile(tmp_path):
    path = tmp_path / ".webos/tv/novacom-devices.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([{"name": "lab-tv", "host": "192.0.2.50"}]))
    return tmp_path


@pytest.mark.parametrize("ports", [{}, {3000: True}])
def test_unavailable_tv_is_success_and_does_not_attempt_install(tmp_path, ports):
    home = home_with_profile(tmp_path)
    def forbidden(*args):
        raise AssertionError("No device verification or install when offline")
    cli = SimpleNamespace(verify_device=forbidden, main=forbidden)
    assert mod.run(home=home, cli=cli, probe=lambda h, p: ports.get(p, False)) == 0


def test_online_tv_installs_both_apps_without_launch(tmp_path):
    home = home_with_profile(tmp_path)
    calls = []
    def verify(device, host):
        calls.append(("verify", device, host))
    def install():
        calls.append(("install", tuple(mod.sys.argv)))
        return 0
    cli = SimpleNamespace(verify_device=verify, main=install)
    assert mod.run(home=home, cli=cli, probe=lambda h, p: True) == 0
    assert calls[0] == ("verify", "lab-tv", "192.0.2.50")
    assert calls[1][1][1:3] == ("all", "--replace")
    assert "--install" in calls[1][1] and "--launch" not in calls[1][1]


def test_online_failure_is_not_hidden(tmp_path):
    home = home_with_profile(tmp_path)
    cli = SimpleNamespace(verify_device=lambda *args: None, main=lambda: 1)
    with pytest.raises(RuntimeError, match="installation failed"):
        mod.run(home=home, cli=cli, probe=lambda h, p: True)


def test_profile_missing_fails_even_when_tv_offline(tmp_path):
    with pytest.raises(FileNotFoundError):
        mod.run(home=tmp_path, probe=lambda h, p: False)


def test_online_identity_mismatch_fails(tmp_path):
    home = home_with_profile(tmp_path)
    def reject(*args):
        raise ValueError("certificate pin mismatch")
    cli = SimpleNamespace(verify_device=reject, main=lambda: 0)
    with pytest.raises(ValueError, match="certificate"):
        mod.run(home=home, cli=cli, probe=lambda h, p: True)
