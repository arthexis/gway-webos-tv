"""Exercise bscpylgtv against a local TLS webOS emulator, without live TV access."""

import asyncio
import json
import logging
import ssl
import subprocess
from contextlib import asynccontextmanager

import pytest
from websockets.asyncio.server import serve

from gway_webos_tv.client import TV
from gway_webos_tv.state import Device, TVError


@pytest.fixture(scope="module")
def tls_context(tmp_path_factory):
    path = tmp_path_factory.mktemp("tls")
    key, certificate = path / "key.pem", path / "certificate.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=loopback-webos-test",
            "-keyout",
            str(key),
            "-out",
            str(certificate),
        ],
        check=True,
        capture_output=True,
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate, key)
    return context


@asynccontextmanager
async def emulator(context, *, switch=True, input_error=False, foreign_input=False):
    messages = []
    foreground = "com.webos.app.browser"
    port = 0

    async def handler(ws):
        nonlocal foreground
        if ws.request.path == "/input":
            async for raw in ws:
                messages.append({"input": raw})
            return
        async for raw in ws:
            message = json.loads(raw)
            messages.append(message)
            uid = message.get("id")
            if message["type"] == "hello":
                response = {
                    "id": uid,
                    "type": "hello",
                    "payload": {"deviceType": "tv", "deviceOS": "webOS"},
                }
            elif message["type"] == "register":
                if not message["payload"].get("client-key"):
                    await ws.send(
                        json.dumps(
                            {"id": uid, "type": "response", "payload": {"pairingType": "PROMPT"}}
                        )
                    )
                response = {
                    "id": uid,
                    "type": "registered",
                    "payload": {"client-key": "test-pair-key"},
                }
            else:
                uri = message["uri"]
                payload = {"returnValue": True}
                if uri.endswith("system/getSystemInfo"):
                    payload["modelName"] = "TEST-TV"
                elif uri.endswith("tv/getExternalInputList"):
                    payload["devices"] = [
                        {
                            "id": "HDMI_2",
                            "label": "PC",
                            "connected": True,
                            "appId": "com.webos.app.hdmi2",
                        }
                    ]
                elif uri.endswith("getForegroundAppInfo"):
                    payload["appId"] = foreground
                elif uri.endswith("tv/switchInput"):
                    if switch:
                        foreground = "com.webos.app.hdmi2"
                elif uri.endswith("tv/executeOneShot"):
                    payload["imageUri"] = "http://127.0.0.1/capture.jpg"
                elif uri.endswith("applicationManager/listApps"):
                    payload["apps"] = [{"id": "com.webos.app.browser", "title": "Browser"}]
                elif uri.endswith("system.launcher/launch"):
                    foreground = message["payload"]["id"]
                elif uri.endswith("getPointerInputSocket"):
                    if input_error:
                        await ws.send(
                            json.dumps(
                                {
                                    "id": uid,
                                    "type": "error",
                                    "error": "401 test-secret-private-path",
                                }
                            )
                        )
                        continue
                    host = "192.0.2.51" if foreign_input else "127.0.0.1"
                    payload["socketPath"] = f"wss://{host}:{port}/input"
                response = {"id": uid, "type": "response", "payload": payload}
            await ws.send(json.dumps(response))

    logger = logging.getLogger("test.webos.server")
    logger.setLevel(logging.CRITICAL)  # TLS preflight closes before the HTTP upgrade.
    async with serve(handler, "127.0.0.1", 0, ssl=context, logger=logger) as server:
        port = server.sockets[0].getsockname()[1]
        yield port, messages


def test_real_library_pair_status_hdmi_and_native_capture(tls_context):
    async def scenario():
        async with emulator(tls_context) as (port, messages):
            device = Device("127.0.0.1")
            tv = TV(device, port=port, timeout=3)
            try:
                await tv.connect(pair=True)
                assert device.client_key == "test-pair-key"
                assert len(device.fingerprint) == 64
                assert (await tv.status())["foreground_app"] == "com.webos.app.browser"
                assert (await tv.hdmi(2, wait=1))["verified"]
                capture = await tv.call(tv.client.take_screenshot())
                assert capture["imageUri"].endswith("capture.jpg")
                assert (await tv.apps())[0]["title"] == "Browser"
                assert (await tv.launch("com.webos.app.browser", wait=1))["verified"]
                assert not any(x.get("type") == "subscribe" for x in messages)
                assert "CONTROL_DISPLAY" in messages[1]["payload"]["manifest"]["permissions"]
            finally:
                await tv.close()

    asyncio.run(scenario())


def test_changed_certificate_never_sends_pairing_key(tls_context):
    async def scenario():
        async with emulator(tls_context) as (port, messages):
            tv = TV(Device("127.0.0.1", "never-send-this-key", "0" * 64), port=port, timeout=3)
            with pytest.raises(TVError, match="no pairing key was sent"):
                await tv.connect()
            assert messages == []

    asyncio.run(scenario())


def test_accepted_switch_is_not_success_until_foreground_changes(tls_context):
    async def scenario():
        async with emulator(tls_context, switch=False) as (port, messages):
            tv = TV(Device("127.0.0.1"), port=port, timeout=3)
            try:
                await tv.connect(pair=True)
                with pytest.raises(TVError, match="not confirmed"):
                    await tv.hdmi(2, wait=0)
                assert any(x.get("uri", "").endswith("switchInput") for x in messages)
            finally:
                await tv.close()

    asyncio.run(scenario())


def test_missing_pairing_does_not_contact_tv():
    async def scenario():
        with pytest.raises(TVError, match="require saved pairing"):
            await TV(Device("192.0.2.50")).connect()

    asyncio.run(scenario())


def test_sdk_exception_body_is_not_exposed():
    async def rejected():
        raise RuntimeError("401 insufficient permissions; client-key=test-secret; imageUri=private")

    async def scenario():
        with pytest.raises(TVError) as caught:
            await TV(Device("192.0.2.50")).call(rejected())
        assert "test-secret" not in str(caught.value)
        assert "imageUri" not in str(caught.value)
        assert "denied permission" in str(caught.value)

    asyncio.run(scenario())


def test_remote_buttons_use_pinned_input_socket(tls_context):
    async def scenario():
        async with emulator(tls_context) as (port, messages):
            tv = TV(Device("127.0.0.1"), port=port, timeout=3)
            try:
                await tv.connect(pair=True)
                await tv.press("ENTER")
                await asyncio.sleep(0.05)
                assert {"input": "type:button\nname:ENTER\n\n"} in messages
            finally:
                await tv.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("mode,match", [("denied", "denied permission"), ("foreign", "paired TV")])
def test_remote_input_rejects_permission_failures_and_foreign_socket(tls_context, mode, match):
    async def scenario():
        async with emulator(
            tls_context, input_error=mode == "denied", foreign_input=mode == "foreign"
        ) as (port, messages):
            tv = TV(Device("127.0.0.1"), port=port, timeout=3)
            try:
                await tv.connect(pair=True)
                with pytest.raises(TVError, match=match) as caught:
                    await tv.press("ENTER")
                assert "test-secret" not in str(caught.value)
                assert not any("input" in message for message in messages)
            finally:
                await tv.close()

    asyncio.run(scenario())
