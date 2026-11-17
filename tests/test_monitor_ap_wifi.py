"""AP join QR: active-only secrets, noncached WSS and TV privacy boundaries."""
import asyncio
import hashlib
import json
import re
import subprocess
from unittest.mock import patch

import pytest

from gway_webos_tv import ap_wifi
from gway_webos_tv.event_bridge import Bridge, write_private

PROFILE = "123e4567-e89b-12d3-a456-426614174000"
SSID = 'Kiosk;Lab:"A"'
KEY = r"test\secret;:,XYZ123"


def fake_reader(*args):
    if args[-4:] == ("device", "show", "wlan0"):
        return PROFILE
    if args[:1] == ("ip",):
        return json.dumps([{"addr_info": [
            {"family": "inet", "local": "10.42.0.1", "prefixlen": 16, "scope": "global"}
        ]}])
    if args[-3:] != ("connection", "show", PROFILE):
        raise AssertionError("unexpected NM profile")
    prop = args[args.index("-g") + 1]
    return {
        "802-11-wireless.mode": "ap",
        "802-11-wireless.ssid": SSID,
        "802-11-wireless-security.key-mgmt": "wpa-psk",
        "802-11-wireless-security.psk": KEY,
    }[prop]


def test_active_profile_only_and_valid_wifi_qr():
    result = ap_wifi.current_ap(fake_reader)
    assert result["available"] is True
    assert result["ssid"] == SSID
    assert result["password"] == KEY
    assert result["gateway"] == "10.42.0.1"
    assert result["subnet"] == "10.42.0.0/16"
    assert result["portal_url"] == "http://10.42.0.1"
    rows = result["qr"]
    assert 21 <= len(rows) <= 185
    assert all(len(row) == len(rows) and re.fullmatch("[01]+", row) for row in rows)
    expected = r'WIFI:T:WPA;S:Kiosk\;Lab\:\\"A\\";P:test\\secret\;\:\,XYZ123;;'
    assert ap_wifi.wifi_escape(SSID) == r'Kiosk\;Lab\:\"A\"'
    assert ap_wifi.wifi_escape(KEY) == r'test\\secret\;\:\,XYZ123'
    assert rows == ap_wifi.qr_matrix(SSID, KEY)
    assert ap_wifi.qr_matrix(SSID, KEY) != ap_wifi.qr_matrix(SSID, "different1234")


@pytest.mark.parametrize("overrides", [
    {"802-11-wireless.mode": "infrastructure"},
    {"802-11-wireless-security.psk": "********"},
    {"802-11-wireless-security.psk": ""},
    {"802-11-wireless-security.psk": "short"},
    {"802-11-wireless-security.key-mgmt": "open"},
    {"802-11-wireless.ssid": "\nrogue"},
])
def test_ap_absent_or_invalid_key_fails_closed(overrides):
    def read(*args):
        if "-g" in args and args[args.index("-g") + 1] in overrides:
            return overrides[args[args.index("-g") + 1]]
        return fake_reader(*args)
    assert ap_wifi.current_ap(read) == {"available": False}


def test_no_fallback_to_uplink_or_leak_of_nmcli_stderr():
    def fail(*args):
        if "wlan0" in args:
            return ""
        raise subprocess.CalledProcessError(1, args, output="secret", stderr="key")
    assert ap_wifi.current_ap(fail) == {"available": False}


def test_rotation_reads_fresh_key_every_time():
    calls = []
    def read(*args):
        calls.append(args)
        if "802-11-wireless-security.psk" in args:
            return "oldsecret1234" if sum(
                "802-11-wireless-security.psk" in a for a in calls
            ) == 1 else "newsecret5678"
        return fake_reader(*args)
    a = ap_wifi.current_ap(read)
    b = ap_wifi.current_ap(read)
    assert a["password"] == "oldsecret1234"
    assert b["password"] == "newsecret5678"
    assert a["qr"] != b["qr"]


class Socket:
    def __init__(self, messages):
        self.messages = iter(json.dumps(m) for m in messages)
        self.sent = []
        self.closed = None
        self.request = type("Request", (), {"path": "/"})()

    async def recv(self):
        return next(self.messages)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.messages)
        except StopIteration:
            raise StopAsyncIteration from None

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def close(self, code, reason):
        self.closed = code


def test_only_paired_monitor_can_request_uncached_wifi(tmp_path, monkeypatch):
    monitor_token, remote_token = "tv-monitor", "remote-legacy"
    write_private(tmp_path / "credential.json", {
        "sha256": hashlib.sha256(remote_token.encode()).hexdigest(),
        "scoped": {
            hashlib.sha256(monitor_token.encode()).hexdigest(): ["monitor.read"]
        },
    })
    bridge = Bridge(tmp_path)
    counter = []
    def sample():
        counter.append(1)
        return {"type": "monitor.wifi", "wifi": {
            "available": True, "password": "test-key-" + str(len(counter)),
            "qr": ["0" * 21] * 21,
        }}
    monkeypatch.setattr(ap_wifi, "wifi_message", sample)

    async def run():
        legitimate = Socket([
            {"type": "auth", "credential": monitor_token},
            {"type": "monitor.wifi"},
            {"type": "monitor.wifi"},
        ])
        await bridge.handler(legitimate)
        assert legitimate.sent[0] == {"type": "ready"}
        assert legitimate.sent[1]["wifi"]["password"] == "test-key-1"
        assert legitimate.sent[2]["wifi"]["password"] == "test-key-2"
        assert bridge.monitor_cache is None
        assert not any(tmp_path.glob("*wifi*"))

        remote = Socket([
            {"type": "auth", "credential": remote_token},
            {"type": "monitor.wifi"},
        ])
        await bridge.handler(remote)
        assert remote.closed == 1008
        assert remote.sent == [{"type": "ready"}]

        anonymous = Socket([{"type": "monitor.wifi"}])
        await bridge.handler(anonymous)
        assert anonymous.closed == 1008

    asyncio.run(run())
