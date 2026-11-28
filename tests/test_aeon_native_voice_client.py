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
