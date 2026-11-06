import json
import stat

import pytest

from gway_webos_tv.cli import main
from gway_webos_tv.state import Device, TVError, default_state_path, load_state, save_state


def test_private_roundtrip_and_no_secret_repr(tmp_path):
    path = tmp_path / "private/device.json"
    device = Device("192.0.2.50", "test-key-not-a-secret", "a" * 64, "TEST-TV")
    save_state(path, device)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert load_state(path) == device
    assert "test-key-not-a-secret" not in repr(device)
    assert not list(path.parent.glob(".device-*"))


def test_world_readable_key_is_rejected(tmp_path):
    path = tmp_path / "device.json"
    save_state(path, Device("192.0.2.50", "test-key", "a" * 64))
    path.chmod(0o644)
    with pytest.raises(TVError, match="0600"):
        load_state(path)


def test_missing_state_never_pairs(tmp_path, capsys):
    assert main(["--state", str(tmp_path / "absent.json"), "--json", "status"]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is False
    assert "No saved pairing" in output["error"]


def test_existing_pairing_reused_without_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.delenv("GWAY_TV_STATE", raising=False)
    legacy = tmp_path / "webos-tv/documentation-tv.json"
    save_state(legacy, Device("192.0.2.50", "test-key", "a" * 64))
    assert default_state_path() == legacy
    assert not (tmp_path / "gway-webos-tv").exists()
    save_state(tmp_path / "webos-tv/another-tv.json", Device("192.0.2.51", "key", "b" * 64))
    assert default_state_path() == tmp_path / "gway-webos-tv/device.json"


def test_invalid_state_does_not_echo_contents(tmp_path, capsys):
    path = tmp_path / "device.json"
    path.write_text('{"client-key":"test-key-not-for-output"')
    path.chmod(0o600)
    assert main(["--state", str(path), "status"]) == 1
    captured = capsys.readouterr()
    assert "test-key-not-for-output" not in captured.err + captured.out
