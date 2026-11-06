import asyncio
import hashlib
import json
import time

from gway_webos_tv.event_bridge import Bridge, write_private


class Socket:
    def __init__(self, message):
        self.message = json.dumps(message)
        self.request = type("Request", (), {"path": "/"})()
        self.sent = []
        self.closed = None

    async def recv(self):
        return self.message

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def close(self, code, reason):
        self.closed = code

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


def test_scoped_credentials_and_legacy_migration(tmp_path):
    async def check():
        bridge = Bridge(tmp_path)
        legacy = hashlib.sha256(b"old-remote").hexdigest()
        write_private(tmp_path / "credential.json", {"sha256": legacy})
        assert bridge.authorized(legacy, "button.pressed")
        assert not bridge.authorized(legacy, "monitor.read")
        secret = "123456"
        salt = "abcd"
        write_private(tmp_path / "pending-pairing.json", {
            "sha256": hashlib.sha256((salt + secret).encode()).hexdigest(),
            "salt": salt, "expires": time.time() + 120, "attempts_remaining": 5
        })
        ws = Socket({"type": "pair", "secret": secret, "app": "gway-monitor"})
        await bridge.handler(ws)
        assert ws.sent[0]["type"] == "paired"
        digest = hashlib.sha256(ws.sent[0]["credential"].encode()).hexdigest()
        assert bridge.authorized(digest, "monitor.read")
        assert not bridge.authorized(digest, "button.pressed")
        assert bridge.authorized(legacy, "button.pressed")
        assert not bridge.authorized(legacy, "monitor.read")
    asyncio.run(check())
