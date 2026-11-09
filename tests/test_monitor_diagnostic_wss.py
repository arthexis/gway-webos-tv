"""WSS diagnostics require separate read and TV response capabilities."""
import asyncio
import hashlib
import json
from gway_webos_tv.event_bridge import Bridge, write_private


def test_diagnostic_denied_to_unprivileged_client(tmp_path):
    credential = "viewer"
    write_private(tmp_path / "credential.json", {
        "sha256": None, "additional_sha256": [],
        "scoped": {hashlib.sha256(credential.encode()).hexdigest(): ["monitor.read"]}
    })

    class Socket:
        request = type("Request", (), {"path": "/"})()
        closed = None
        sent = []
        def __init__(self):
            self.messages = iter([json.dumps({"type": "monitor.diagnostic.request",
                                               "repository": "arthexis/gway-agent-ops"})])
        async def recv(self):
            return json.dumps({"type": "auth", "credential": credential})
        async def send(self, raw):
            self.sent.append(json.loads(raw))
        async def close(self, code, reason):
            self.closed = code
        def __aiter__(self):
            return self
        async def __anext__(self):
            try:
                return next(self.messages)
            except StopIteration:
                raise StopAsyncIteration

    async def check():
        sock = Socket()
        await Bridge(tmp_path).handler(sock)
        assert sock.sent[0]["type"] == "ready"
        assert sock.closed == 1008

    asyncio.run(check())


def test_nonce_response_requires_registered_session(tmp_path):
    bridge = Bridge(tmp_path)
    assert bridge.diagnostic_pending is None
    assert bridge.diagnostic_tv is None
    assert not bridge.authorized("invalid", "monitor.diagnostic.read")
