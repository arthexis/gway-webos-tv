"""Characterization tests for the existing monitor/remote-test capability boundary.

These tests intentionally exercise the current bridge protocol before modularization.
"""
import asyncio
import hashlib
import json
import time

from gway_webos_tv.event_bridge import Bridge, write_private


class FakeSocket:
    def __init__(self, messages):
        self.messages = iter(json.dumps(message) for message in messages)
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
        self.closed = (code, reason)


def test_monitor_credential_cannot_send_buttons_and_remote_cannot_read(tmp_path):
    bridge = Bridge(tmp_path)
    monitor_token = "monitor-only"
    remote_token = "remote-only"
    write_private(
        tmp_path / "credential.json",
        {
            "sha256": None,
            "additional_sha256": [],
            "scoped": {
                hashlib.sha256(monitor_token.encode()).hexdigest(): ["monitor.read"],
                hashlib.sha256(remote_token.encode()).hexdigest(): ["button.pressed"],
            },
        },
    )

    async def run():
        monitor = FakeSocket([
            {"type": "auth", "credential": monitor_token},
            {"type": "button.pressed", "code": 403},
        ])
        await bridge.handler(monitor)
        assert monitor.sent == [{"type": "ready"}]
        assert monitor.closed[0] == 1008
        assert not (tmp_path / "last-button.json").exists()

        remote = FakeSocket([
            {"type": "auth", "credential": remote_token},
            {"type": "monitor.read"},
        ])
        await bridge.handler(remote)
        assert remote.sent == [{"type": "ready"}]
        assert remote.closed[0] == 1008

    asyncio.run(run())


def test_monitor_cache_reuses_snapshot_inside_ttl(tmp_path, monkeypatch):
    bridge = Bridge(tmp_path)
    calls = []

    def fake_snapshot():
        calls.append(time.monotonic())
        return {"type": "monitor.snapshot", "observed_at": "2026-01-01T00:00:00Z"}

    monkeypatch.setattr("gway_webos_tv.event_bridge.snapshot", fake_snapshot)

    async def run():
        first = await bridge.monitor()
        second = await bridge.monitor()
        assert first is second
        assert len(calls) == 1
        bridge.monitor_cached_at -= 11
        third = await bridge.monitor()
        assert len(calls) == 2
        assert third == first

    asyncio.run(run())
