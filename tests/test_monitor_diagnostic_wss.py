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


def test_two_authenticated_clients_nonce_replay_and_expiry(tmp_path):
    import time
    from websockets.asyncio.server import serve
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosed

    viewer, tv = "operator", "tv-credential"
    write_private(tmp_path / "credential.json", {
        "sha256": None, "additional_sha256": [],
        "scoped": {
            hashlib.sha256(viewer.encode()).hexdigest(): ["monitor.diagnostic.read"],
            hashlib.sha256(tv.encode()).hexdigest(): ["monitor.read", "monitor.diagnostic.respond"],
        }
    })
    bridge = Bridge(tmp_path)

    async def check():
        async with serve(bridge.handler, "127.0.0.1", 0, max_size=2048) as server:
            url = "ws://127.0.0.1:" + str(server.sockets[0].getsockname()[1])
            async with connect(url) as tv_ws, connect(url) as operator:
                await tv_ws.send(json.dumps({"type": "auth", "credential": tv}))
                assert json.loads(await tv_ws.recv())["type"] == "ready"
                await tv_ws.send(json.dumps({"type": "monitor.diagnostic.register"}))
                await operator.send(json.dumps({"type": "auth", "credential": viewer}))
                assert json.loads(await operator.recv())["type"] == "ready"
                await operator.send(json.dumps({"type": "monitor.diagnostic.request",
                                                "repository": "arthexis/gway-agent-ops"}))
                challenge = json.loads(await asyncio.wait_for(tv_ws.recv(), 2))
                assert challenge["type"] == "monitor.diagnostic.request"
                assert len(challenge["nonce"]) == 32
                assert challenge["expires_at"] > time.time() * 1000
                result = {"type": "monitor.diagnostic.result", "nonce": challenge["nonce"],
                          "git_sha": "a" * 40, "build_id": "aaaaaaaaaaaaaaaa",
                          "channel": "deployments", "visible": True,
                          "card": {"repository": "arthexis/gway-agent-ops",
                                   "badge": "Installed", "aria_label": "Installed"}}
                await tv_ws.send(json.dumps(result))
                assert json.loads(await asyncio.wait_for(operator.recv(), 2))["card"]["badge"] == "Installed"
                await tv_ws.send(json.dumps(result))
                try:
                    await asyncio.wait_for(tv_ws.recv(), 2)
                    assert False, "replayed response accepted"
                except ConnectionClosed as error:
                    assert error.rcvd.code == 1008

    asyncio.run(check())


def test_diagnostic_operator_cannot_register_as_tv(tmp_path):
    from websockets.asyncio.server import serve
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosed

    write_private(tmp_path / "credential.json", {
        "sha256": None, "additional_sha256": [],
        "scoped": {hashlib.sha256(b"operator").hexdigest(): ["monitor.diagnostic.read", "monitor.read"]}
    })

    async def check():
        async with serve(Bridge(tmp_path).handler, "127.0.0.1", 0) as server:
            url = "ws://127.0.0.1:" + str(server.sockets[0].getsockname()[1])
            async with connect(url) as ws:
                await ws.send(json.dumps({"type": "auth", "credential": "operator"}))
                assert json.loads(await ws.recv())["type"] == "ready"
                await ws.send(json.dumps({"type": "monitor.diagnostic.register"}))
                try:
                    await asyncio.wait_for(ws.recv(), 2)
                    assert False, "operator registered as TV"
                except ConnectionClosed as error:
                    assert error.rcvd.code == 1008

    asyncio.run(check())


def test_expired_nonce_and_disconnected_tv_fail_closed(tmp_path):
    import time
    from websockets.asyncio.server import serve
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosed

    tv, operator = "tv", "operator"
    write_private(tmp_path / "credential.json", {
        "sha256": None, "additional_sha256": [],
        "scoped": {
            hashlib.sha256(tv.encode()).hexdigest(): ["monitor.read", "monitor.diagnostic.respond"],
            hashlib.sha256(operator.encode()).hexdigest(): ["monitor.diagnostic.read"]
        }
    })
    bridge = Bridge(tmp_path)

    async def check():
        async with serve(bridge.handler, "127.0.0.1", 0) as server:
            url = "ws://127.0.0.1:" + str(server.sockets[0].getsockname()[1])
            async with connect(url) as tv_ws, connect(url) as op:
                await tv_ws.send(json.dumps({"type": "auth", "credential": tv}))
                await tv_ws.recv()
                await tv_ws.send(json.dumps({"type": "monitor.diagnostic.register"}))
                await op.send(json.dumps({"type": "auth", "credential": operator}))
                await op.recv()
                await op.send(json.dumps({"type": "monitor.diagnostic.request",
                                          "repository": "arthexis/gway-agent-ops"}))
                challenge = json.loads(await asyncio.wait_for(tv_ws.recv(), 2))
                # Simulate a server-side expired nonce without sleeping.
                nonce, registered, future, _ = bridge.diagnostic_pending
                bridge.diagnostic_pending = (nonce, registered, future, time.monotonic() - 1)
                await tv_ws.send(json.dumps({"type": "monitor.diagnostic.result",
                                              "nonce": challenge["nonce"],
                                              "git_sha": "a" * 40, "build_id": "abc",
                                              "channel": "deployments", "visible": True,
                                              "card": None}))
                try:
                    await asyncio.wait_for(tv_ws.recv(), 2)
                    assert False, "expired nonce accepted"
                except ConnectionClosed as error:
                    assert error.rcvd.code == 1008
                assert json.loads(await asyncio.wait_for(op.recv(), 2))["type"] == "monitor.diagnostic.unavailable"
            assert bridge.diagnostic_tv is None

    asyncio.run(check())
