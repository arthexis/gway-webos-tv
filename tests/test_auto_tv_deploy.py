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


@pytest.mark.parametrize("ports, expected", [
    ({}, mod.TV_DEFERRED),
    ({3000: True}, mod.TV_DEVELOPER_UNAVAILABLE),
])
def test_deferred_tv_does_not_claim_installation(tmp_path, ports, expected):
    home = home_with_profile(tmp_path)
    def forbidden(*args):
        raise AssertionError("No installation while TV is unavailable")
    cli = SimpleNamespace(verify_device=forbidden, main=forbidden)
    assert mod.run(home=home, cli=cli, probe=lambda h, p: ports.get(p, False),
                   require_online=True) == expected


def test_online_tv_installs_both_apps_without_launch(tmp_path):
    home = home_with_profile(tmp_path)
    calls = []
    def verify(device, host):
        calls.append(("verify", device, host))
    def install():
        calls.append(("install", tuple(mod.sys.argv)))
        return 0
    cli = SimpleNamespace(verify_device=verify, main=install, tv_status=lambda host: {"foreground_app": "com.webos.app.browser"}, discover_apps=lambda: ["gway-monitor", "remote-test"], load_manifest=lambda p: ({}, {"id": "com.example." + p.name}))
    assert mod.run(home=home, cli=cli, probe=lambda h, p: True) == 0
    assert calls[0] == ("verify", "lab-tv", "192.0.2.50")
    assert calls[1][1][1:3] == ("all", "--replace")
    assert "--install" in calls[1][1] and "--launch" not in calls[1][1]


def test_online_failure_is_not_hidden(tmp_path):
    home = home_with_profile(tmp_path)
    cli = SimpleNamespace(verify_device=lambda *args: None, main=lambda: 1, tv_status=lambda host: {"foreground_app": None})
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


def test_foreground_updated_app_is_restarted(tmp_path):
    home = home_with_profile(tmp_path)
    calls = []
    app_id = "com.example.gway-monitor"
    cli = SimpleNamespace(
        verify_device=lambda *args: None,
        tv_status=lambda host: {"foreground_app": app_id},
        main=lambda: 0,
        discover_apps=lambda: ["gway-monitor", "remote-test"],
        load_manifest=lambda p: ({}, {"id": "com.example." + p.name}),
        command=lambda *args: calls.append(args),
    )
    assert mod.run(home=home, cli=cli, probe=lambda h, p: True) == 0
    assert calls == [
        ("ares-launch", "--device", "lab-tv", "--close", app_id),
        ("ares-launch", "--device", "lab-tv", app_id),
    ]


def test_foreground_changed_during_install_is_not_overridden(tmp_path):
    home = home_with_profile(tmp_path)
    calls = []
    states = iter(["com.example.gway-monitor", "com.webos.app.browser"])
    cli = SimpleNamespace(
        verify_device=lambda *args: None,
        tv_status=lambda host: {"foreground_app": next(states)},
        main=lambda: 0,
        discover_apps=lambda: ["gway-monitor"],
        load_manifest=lambda p: ({}, {"id": "com.example.gway-monitor"}),
        command=lambda *args: calls.append(args),
    )
    assert mod.run(home=home, cli=cli, probe=lambda h, p: True) == 0
    assert calls == []
