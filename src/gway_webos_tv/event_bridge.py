"""TLS-only paired event receiver for the webOS remote test app."""

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import ssl
import tempfile
import time
from pathlib import Path

from websockets.asyncio.server import serve

from .monitor import snapshot


def state_directory():
    return (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "gway-webos-tv"
        / "bridge"
    )


def write_private(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".bridge-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def button_names_path():
    return (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "gway-webos-tv/button-names.json"
    )


def button_name(path, code):
    """Read only the requested override; missing or invalid entries use app defaults."""
    try:
        names = json.loads(path.read_text())
        name = names.get(str(code)) if isinstance(names, dict) else None
    except (OSError, ValueError):
        return None
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        return None
    return name if all(ord(char) >= 32 for char in name) else None


class Bridge:
    def __init__(self, directory, names_path=None):
        self.directory = directory
        self.names_path = names_path if names_path is not None else button_names_path()
        self.lock = asyncio.Lock()
        self.monitor_lock = asyncio.Lock()
        self.monitor_cache = None
        self.monitor_cached_at = 0

    async def monitor(self):
        async with self.monitor_lock:
            if self.monitor_cache is None or time.monotonic() - self.monitor_cached_at >= 10:
                self.monitor_cache = await asyncio.to_thread(snapshot)
                self.monitor_cached_at = time.monotonic()
            return self.monitor_cache

    def authorized(self, digest):
        try:
            record = json.loads((self.directory / "credential.json").read_text())
            hashes = [record.get("sha256")] + record.get("additional_sha256", [])
            return any(
                isinstance(item, str) and hmac.compare_digest(digest, item) for item in hashes
            )
        except (OSError, ValueError, TypeError, AttributeError):
            return False

    async def handler(self, ws):
        try:
            raw = await asyncio.wait_for(ws.recv(), 10)
            message = json.loads(raw)
            if not isinstance(message, dict):
                return
            if message.get("type") == "admin.arm_pairing":
                if ws.request.path != "/admin/pair":
                    await ws.close(1008, "Unsupported operation")
                    return
                try:
                    expected = json.loads((self.directory / "admin.json").read_text())["sha256"]
                except (OSError, ValueError, KeyError, TypeError):
                    expected = ""
                credential = message.get("credential")
                salt, digest = message.get("salt"), message.get("sha256")
                if (
                    not isinstance(credential, str)
                    or not isinstance(expected, str)
                    or not hmac.compare_digest(
                        hashlib.sha256(credential.encode()).hexdigest(), expected
                    )
                    or not isinstance(salt, str)
                    or not re.fullmatch(r"[0-9a-f]{32}", salt)
                    or not isinstance(digest, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", digest)
                ):
                    await ws.close(1008, "Authorization denied")
                    return
                async with self.lock:
                    write_private(
                        self.directory / "pending-pairing.json",
                        {
                            "sha256": digest,
                            "salt": salt,
                            "expires": time.time() + 120,
                            "attempts_remaining": 5,
                        },
                    )
                await ws.send(json.dumps({"type": "pairing.open", "expires_in": 120}))
                return
            if message.get("type") == "pair":
                async with self.lock:
                    value = message.get("secret")
                    pending_path = self.directory / "pending-pairing.json"
                    valid = False
                    try:
                        pending = json.loads(pending_path.read_text())
                        expires = pending["expires"]
                        remaining = pending["attempts_remaining"]
                        salt, expected = pending["salt"], pending["sha256"]
                        if (
                            not isinstance(expires, (int, float))
                            or not isinstance(remaining, int)
                            or not 1 <= remaining <= 5
                            or not isinstance(salt, str)
                            or not isinstance(expected, str)
                            or time.time() > expires
                        ):
                            pending_path.unlink(missing_ok=True)
                        else:
                            pending["attempts_remaining"] = remaining - 1
                            if remaining == 1:
                                pending_path.unlink(missing_ok=True)
                            else:
                                write_private(pending_path, pending)
                            if isinstance(value, str) and re.fullmatch(r"[0-9]{6}", value):
                                digest = hashlib.sha256((salt + value).encode()).hexdigest()
                                valid = hmac.compare_digest(digest, expected)
                    except (OSError, ValueError, KeyError, TypeError):
                        pass
                    if not valid:
                        await ws.close(1008, "Pairing denied")
                        return
                    pending_path.unlink(missing_ok=True)
                    credential = secrets.token_urlsafe(32)
                    try:
                        old = json.loads((self.directory / "credential.json").read_text())
                    except FileNotFoundError:
                        old = {}
                    existing = [old.get("sha256")] + old.get("additional_sha256", [])
                    existing = [item for item in existing if isinstance(item, str)]
                    if len(existing) >= 16:
                        await ws.close(1008, "Pairing capacity reached")
                        return
                    session_digest = hashlib.sha256(credential.encode()).hexdigest()
                    write_private(
                        self.directory / "credential.json",
                        {
                            "sha256": existing[0] if existing else session_digest,
                            "additional_sha256": (existing[1:] + [session_digest])
                            if existing
                            else [],
                        },
                    )
                    (self.directory / "last-button.json").unlink(missing_ok=True)
                await ws.send(json.dumps({"type": "paired", "credential": credential}))
            elif message.get("type") == "auth":
                value = message.get("credential")
                session_digest = (
                    hashlib.sha256(value.encode()).hexdigest() if isinstance(value, str) else ""
                )
                if not self.authorized(session_digest):
                    await ws.close(1008, "Authentication denied")
                    return
                await ws.send(json.dumps({"type": "ready"}))
            else:
                await ws.close(1008, "Authentication required")
                return
            async for raw in ws:
                if not self.authorized(session_digest):
                    await ws.close(1008, "Credential revoked")
                    return
                data = json.loads(raw)
                if isinstance(data, dict) and data.get("type") == "monitor.read":
                    await ws.send(json.dumps(await self.monitor()))
                    continue
                if not isinstance(data, dict) or data.get("type") != "button.pressed":
                    await ws.close(1008, "Unsupported message")
                    return
                code = data.get("code")
                if type(code) is not int or not 1 <= code <= 65535:
                    await ws.close(1008, "Invalid key code")
                    return
                event_id = data.get("id")
                if event_id is not None and (
                    type(event_id) is not int or not 1 <= event_id <= 9007199254740991
                ):
                    await ws.close(1008, "Invalid event id")
                    return
                write_private(
                    self.directory / "last-button.json", {"code": code, "received_at": time.time()}
                )
                response = {
                    "type": "button.accepted",
                    "code": code,
                    "name": button_name(self.names_path, code),
                }
                if event_id is not None:
                    response["id"] = event_id
                await ws.send(json.dumps(response))
        except (ValueError, asyncio.TimeoutError, OSError):
            await ws.close(1008, "Invalid request")


async def run(args):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.cert, args.key)
    bridge = Bridge(state_directory())
    async with serve(
        bridge.handler, args.listen, args.port, ssl=context, max_size=2048, max_queue=8
    ):
        print("Event bridge running with TLS. Press Ctrl-C to stop.", flush=True)
        await asyncio.Future()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", required=True, help="Local interface address")
    parser.add_argument("--port", type=int, default=8769)
    parser.add_argument("--cert", required=True, help="TV-trusted TLS certificate chain")
    parser.add_argument("--key", required=True, help="TLS private key")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
