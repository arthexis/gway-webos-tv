"""Optional native integration, local TLS and fake audio only."""
import asyncio
import hashlib
import os
import socket
import ssl
import subprocess

import pytest
from websockets.asyncio.server import serve
from gway_webos_tv.aeon_voice import VoiceSession
from gway_webos_tv.event_bridge import Bridge, write_private


@pytest.mark.skipif(not os.getenv("AEON_NATIVE_VOICE_CLIENT"), reason="helper not built")
def test_native_shared_toggle(tmp_path):
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256",
        "-nodes", "-keyout", str(key), "-out", str(cert), "-days", "1",
        "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost",
    ], check=True, capture_output=True)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    fixture = "a" * 43
    write_private(tmp_path / "credential.json", {
        "scoped": {hashlib.sha256(fixture.encode()).hexdigest(): ["aeon.voice"]}
    })

    class Backend:
        starts = stops = 0
        async def start(self, session):
            self.starts += 1
        async def stop(self):
            self.stops += 1

    backend = Backend()
    bridge = Bridge(tmp_path, voice=VoiceSession(backend))

    async def check():
        async with serve(bridge.handler, "127.0.0.1", 0, ssl=context) as server:
            port = server.sockets[0].getsockname()[1]

            async def run_client(hostname, valid):
                parent, child = socket.socketpair()
                parent.setblocking(False)
                read, write = os.pipe()
                os.write(write, fixture.encode())
                os.close(write)
                proc = subprocess.Popen([
                    os.environ["AEON_NATIVE_VOICE_CLIENT"],
                    f"wss://127.0.0.1:{port}/aeon/voice", hostname,
                    str(cert), str(child.fileno()), str(read),
                ], pass_fds=(child.fileno(), read), stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
                child.close()
                os.close(read)
                loop = asyncio.get_running_loop()

                async def expect(state):
                    assert await asyncio.wait_for(loop.sock_recv(parent, 1), 12) == state

                try:
                    if not valid:
                        await expect(b"U")
                        assert backend.starts == 0
                        return
                    await expect(b"S")
                    await loop.sock_sendall(parent, b"M")
                    await expect(b"P")
                    await expect(b"L")
                    await expect(b"L")
                    await loop.sock_sendall(parent, b"C")
                    await expect(b"P")
                    await expect(b"S")
                    assert (backend.starts, backend.stops) == (1, 1)
                    await loop.sock_sendall(parent, b"C")
                    await expect(b"P")
                    await expect(b"L")
                    await loop.sock_sendall(parent, b"Q")
                    for _ in range(40):
                        if bridge.voice.active is None:
                            break
                        await asyncio.sleep(.05)
                    assert (backend.starts, backend.stops) == (2, 2)
                finally:
                    parent.close()
                    if proc.poll() is None:
                        proc.terminate()
                    await asyncio.to_thread(proc.wait, 5)

            await run_client("wrong.local", False)
            await run_client("localhost", True)
    asyncio.run(check())


@pytest.mark.skipif(not os.getenv("AEON_NATIVE_VOICE_CLIENT"), reason="helper not built")
def test_native_voice_pairing(tmp_path):
    import json
    import time
    import stat
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosed

    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt",
                    "ec_paramgen_curve:P-256", "-nodes", "-keyout", str(key),
                    "-out", str(cert), "-days", "1", "-subj", "/CN=localhost",
                    "-addext", "subjectAltName=DNS:localhost"], check=True, capture_output=True)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    code = "123456"
    salt = "a"*32
    existing = hashlib.sha256(b"existing-legacy").hexdigest()
    write_private(tmp_path / "credential.json", {"sha256": existing, "scoped": {}})
    bridge = Bridge(tmp_path)

    def arm(app):
        record = {"sha256": hashlib.sha256((salt+code).encode()).hexdigest(),
                  "salt": salt, "expires": time.time()+120, "attempts_remaining": 5}
        if app:
            record["app"] = app
        write_private(tmp_path / "pending-pairing.json", record)

    async def check():
        async with serve(bridge.handler, "127.0.0.1", 0, ssl=context) as server:
            base = "wss://127.0.0.1:" + str(server.sockets[0].getsockname()[1])
            tls = ssl.create_default_context(cafile=str(cert))
            arm(None)
            async with connect(base+"/aeon/pair", ssl=tls, server_hostname="localhost") as ws:
                await ws.send(json.dumps({"type":"pair","app":"aeon-player","secret":code}))
                with pytest.raises(ConnectionClosed):
                    await ws.recv()
            arm("aeon-player")
            target = tmp_path / "native.credential"
            parent, child = socket.socketpair()
            parent.setblocking(False)
            rd, wr = os.pipe()
            os.write(wr, code.encode()); os.close(wr)
            proc = subprocess.Popen([os.environ["AEON_NATIVE_VOICE_CLIENT"],
                base+"/aeon/pair", "localhost", str(cert), str(child.fileno()), str(rd),
                "--pair", str(target)], pass_fds=(child.fileno(),rd),
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            child.close();os.close(rd)
            try:
                assert await asyncio.wait_for(asyncio.get_running_loop().sock_recv(parent,1),12)==b"S"
                await asyncio.to_thread(proc.wait,5)
                assert stat.S_IMODE(target.stat().st_mode)==0o600
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                assert bridge.voice_authorized(digest)
                assert not bridge.authorized(digest,"button.pressed")
                assert not bridge.authorized(digest,"monitor.read")
                assert bridge.authorized(existing,"button.pressed")
            finally:
                parent.close()
                if proc.poll() is None:
                    proc.kill()
                    await asyncio.to_thread(proc.wait,5)
    asyncio.run(check())
