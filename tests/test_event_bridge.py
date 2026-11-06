import asyncio
import hashlib
import json
import ssl
import subprocess
import time

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from gway_webos_tv.event_bridge import Bridge, write_private


def test_tls_pair_auth_and_button_events(tmp_path):
    key = tmp_path / "key.pem"
    cert = tmp_path / "cert.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost",
        ],
        check=True,
        capture_output=True,
    )
    server_ssl = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ssl.load_cert_chain(cert, key)
    client_ssl = ssl.create_default_context(cafile=str(cert))
    names_path = tmp_path / "button-names.json"
    write_private(names_path, {"13": "OK", "415": "Play"})
    bridge = Bridge(tmp_path / "state", names_path=names_path)
    write_private(
        tmp_path / "state/pending-pairing.json",
        {
            "sha256": hashlib.sha256(b"testsalt012345").hexdigest(),
            "salt": "testsalt",
            "expires": time.time() + 120,
            "attempts_remaining": 5,
        },
    )

    write_private(
        tmp_path / "state/admin.json",
        {"sha256": hashlib.sha256(b"local-admin-test-key").hexdigest()},
    )

    async def check():
        async with serve(bridge.handler, "127.0.0.1", 0, ssl=server_ssl, max_size=2048) as server:
            port = server.sockets[0].getsockname()[1]
            url = f"wss://localhost:{port}"
            async with connect(url, ssl=client_ssl) as ws:
                await ws.send(
                    json.dumps(
                        {
                            "type": "admin.arm_pairing",
                            "credential": "local-admin-test-key",
                            "salt": "a" * 32,
                            "sha256": "b" * 64,
                        }
                    )
                )
                try:
                    await ws.recv()
                    assert False, "admin operation accepted on public path"
                except ConnectionClosed as error:
                    assert error.rcvd.code == 1008
            async with connect(url + "/admin/pair", ssl=client_ssl) as ws:
                await ws.send(
                    json.dumps(
                        {
                            "type": "admin.arm_pairing",
                            "credential": "wrong",
                            "salt": "a" * 32,
                            "sha256": "b" * 64,
                        }
                    )
                )
                try:
                    await ws.recv()
                    assert False, "invalid admin credential accepted"
                except ConnectionClosed as error:
                    assert error.rcvd.code == 1008
            async with connect(url, ssl=client_ssl) as ws:
                await ws.send(json.dumps({"type": "button.pressed", "code": 13}))
                try:
                    await ws.recv()
                    assert False, "unauthenticated event accepted"
                except ConnectionClosed as error:
                    assert error.rcvd.code == 1008
            async with connect(url, ssl=client_ssl) as ws:
                await ws.send(json.dumps({"type": "pair", "secret": "wrong"}))
                try:
                    await ws.recv()
                    assert False, "invalid pairing accepted"
                except ConnectionClosed as error:
                    assert error.rcvd.code == 1008
            async with connect(url, ssl=client_ssl) as ws:
                await ws.send(json.dumps({"type": "pair", "secret": "012345"}))
                credential = json.loads(await ws.recv())["credential"]
                assert credential not in (tmp_path / "state/credential.json").read_text()
                await ws.send(json.dumps({"type": "button.pressed", "code": 403}))
                assert json.loads(await ws.recv())["code"] == 403
            async with connect(url, ssl=client_ssl) as ws:
                await ws.send(json.dumps({"type": "auth", "credential": credential}))
                assert json.loads(await ws.recv())["type"] == "ready"
                await ws.send(json.dumps({"type": "button.pressed", "code": 13, "id": 1}))
                assert json.loads(await ws.recv()) == {
                    "type": "button.accepted",
                    "code": 13,
                    "id": 1,
                    "name": "OK",
                }
                write_private(names_path, {"13": "Select"})
                await ws.send(json.dumps({"type": "button.pressed", "code": 13, "id": 2}))
                assert json.loads(await ws.recv())["name"] == "Select"
                await ws.send(json.dumps({"type": "button.pressed", "code": 415, "id": 3}))
                assert json.loads(await ws.recv())["name"] is None
                assert json.loads((tmp_path / "state/last-button.json").read_text())["code"] == 415
                await ws.send(json.dumps({"type": "run", "command": "anything"}))
                try:
                    await ws.recv()
                    assert False, "command accepted"
                except ConnectionClosed as error:
                    assert error.rcvd.code == 1008

    asyncio.run(check())


def test_pairing_limit_expiry_and_admin_path(tmp_path):
    class FakeSocket:
        def __init__(self, message, path="/"):
            self.message = json.dumps(message)
            self.request = type("Request", (), {"path": path})()
            self.closed = None
            self.sent = []

        async def recv(self):
            return self.message

        async def close(self, code, reason):
            self.closed = code

        async def send(self, value):
            self.sent.append(json.loads(value))

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    async def check():
        bridge = Bridge(tmp_path)
        write_private(tmp_path / "admin.json", {"sha256": hashlib.sha256(b"admin-key").hexdigest()})
        code = "000123"
        salt = "a" * 32
        admin = {
            "type": "admin.arm_pairing",
            "credential": "admin-key",
            "salt": salt,
            "sha256": hashlib.sha256((salt + code).encode()).hexdigest(),
        }
        denied = FakeSocket(admin, "/public")
        await bridge.handler(denied)
        assert denied.closed == 1008
        opened = FakeSocket(admin, "/admin/pair")
        await bridge.handler(opened)
        assert opened.sent[0]["type"] == "pairing.open"
        for _ in range(5):
            wrong = FakeSocket({"type": "pair", "secret": "999999"})
            await bridge.handler(wrong)
            assert wrong.closed == 1008
        assert not (tmp_path / "pending-pairing.json").exists()
        expired = {
            "salt": salt,
            "sha256": admin["sha256"],
            "expires": time.time() - 1,
            "attempts_remaining": 5,
        }
        write_private(tmp_path / "pending-pairing.json", expired)
        denied = FakeSocket({"type": "pair", "secret": code})
        await bridge.handler(denied)
        assert denied.closed == 1008
        assert not (tmp_path / "pending-pairing.json").exists()
        opened = FakeSocket(admin, "/admin/pair")
        await bridge.handler(opened)
        paired = FakeSocket({"type": "pair", "secret": code})
        await bridge.handler(paired)
        assert paired.sent[0]["type"] == "paired"
        assert not (tmp_path / "pending-pairing.json").exists()

    asyncio.run(check())
