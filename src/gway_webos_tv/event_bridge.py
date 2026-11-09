"""TLS-only paired event receiver for the webOS remote test app."""

import argparse
import asyncio
import subprocess
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


def open_local_pairing_window():
    """Create a short-lived, single-use pairing code on the bridge host."""
    code = f"{secrets.randbelow(1000000):06d}"
    salt = secrets.token_hex(16)
    write_private(
        state_directory() / "pending-pairing.json",
        {
            "sha256": hashlib.sha256((salt + code).encode()).hexdigest(),
            "salt": salt,
            "expires": time.time() + 120,
            "attempts_remaining": 5,
        },
    )
    return code


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
        self.deploy_jobs = {}
        self.deploy_lock = asyncio.Lock()
        self.diagnostic_tv = None
        self.diagnostic_tv_digest = None
        self.diagnostic_pending = None
        self.diagnostic_lock = asyncio.Lock()

    async def monitor(self):
        async with self.monitor_lock:
            if self.monitor_cache is None or time.monotonic() - self.monitor_cached_at >= 10:
                self.monitor_cache = await asyncio.to_thread(snapshot)
                self.monitor_cached_at = time.monotonic()
            return self.monitor_cache

    async def retry_deployment(self, repository):
        def execute():
            try:
                result = subprocess.run(
                    ["/usr/local/bin/gway-remote", "deploy", repository, "--follow"],
                    capture_output=True, text=True, timeout=900, check=False,
                )
                return {"success": result.returncode == 0,
                        "error": None if result.returncode == 0 else "Deployment command failed"}
            except (OSError, subprocess.TimeoutExpired):
                return {"success": False, "error": "Deployment command unavailable or timed out"}
        outcome = await asyncio.to_thread(execute)
        async with self.monitor_lock:
            self.monitor_cache = None
        return outcome

    def authorized(self, digest, capability=None):
        try:
            record = json.loads((self.directory / "credential.json").read_text())
            hashes = [record.get("sha256")] + record.get("additional_sha256", [])
            legacy = any(
                isinstance(item, str) and hmac.compare_digest(digest, item) for item in hashes
            )
            if legacy:
                return capability not in ("monitor.read", "deployment.retry",
                                          "monitor.diagnostic.read", "monitor.diagnostic.respond")
            scoped = record.get("scoped", {})
            return (
                isinstance(scoped, dict)
                and isinstance(scoped.get(digest), list)
                and capability in scoped[digest]
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
                    app = message.get("app", "remote-test")
                    if app not in ("remote-test", "gway-monitor"):
                        await ws.close(1008, "Unknown application")
                        return
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
                    scoped = old.get("scoped", {})
                    if not isinstance(scoped, dict):
                        scoped = {}
                    scoped[session_digest] = (
                        ["monitor.read", "deployment.retry", "monitor.diagnostic.respond"] if app == "gway-monitor" else ["button.pressed"]
                    )
                    write_private(
                        self.directory / "credential.json",
                        {
                            "sha256": existing[0] if existing else None,
                            "additional_sha256": existing[1:] if existing else [],
                            "scoped": scoped,
                        },
                    )
                    (self.directory / "last-button.json").unlink(missing_ok=True)
                await ws.send(json.dumps({"type": "paired", "credential": credential}))
            elif message.get("type") == "auth":
                value = message.get("credential")
                session_digest = (
                    hashlib.sha256(value.encode()).hexdigest() if isinstance(value, str) else ""
                )
                if not (
                    self.authorized(session_digest, "monitor.read")
                    or self.authorized(session_digest, "button.pressed")
                    or self.authorized(session_digest, "monitor.diagnostic.read")
                ):
                    await ws.close(1008, "Authentication denied")
                    return
                await ws.send(json.dumps({"type": "ready"}))
            else:
                await ws.close(1008, "Authentication required")
                return
            async for raw in ws:
                if not (
                    self.authorized(session_digest, "monitor.read")
                    or self.authorized(session_digest, "button.pressed")
                    or self.authorized(session_digest, "monitor.diagnostic.read")
                ):
                    await ws.close(1008, "Credential revoked")
                    return
                data = json.loads(raw)
                if isinstance(data, dict) and data.get("type") == "monitor.diagnostic.register":
                    if not self.authorized(session_digest, "monitor.diagnostic.respond"):
                        await ws.close(1008, "Capability denied")
                        return
                    if self.diagnostic_tv is not None and self.diagnostic_tv is not ws:
                        await ws.close(1008, "Diagnostic TV already registered")
                        return
                    self.diagnostic_tv = ws
                    self.diagnostic_tv_digest = session_digest
                    continue
                if isinstance(data, dict) and data.get("type") == "monitor.diagnostic.request":
                    if not self.authorized(session_digest, "monitor.diagnostic.read"):
                        await ws.close(1008, "Capability denied")
                        return
                    if data.get("repository") != "arthexis/gway-agent-ops":
                        await ws.close(1008, "Unsupported diagnostic")
                        return
                    async with self.diagnostic_lock:
                        tv = self.diagnostic_tv
                        if (tv is None or tv is ws or not self.authorized(self.diagnostic_tv_digest, "monitor.diagnostic.respond")):
                            await ws.send(json.dumps({"type": "monitor.diagnostic.unavailable"}))
                            continue
                        nonce = secrets.token_hex(16)
                        future = asyncio.get_running_loop().create_future()
                        self.diagnostic_pending = (nonce, tv, future, time.monotonic() + 5)
                        try:
                            await tv.send(json.dumps({"type": "monitor.diagnostic.request", "nonce": nonce,
                                "expires_at": int(time.time() * 1000) + 5000,
                                "repository": "arthexis/gway-agent-ops"}))
                            try:
                                result = await asyncio.wait_for(future, timeout=5)
                            except asyncio.TimeoutError:
                                result = {"type": "monitor.diagnostic.unavailable"}
                            await ws.send(json.dumps(result))
                        finally:
                            self.diagnostic_pending = None
                    continue
                if isinstance(data, dict) and data.get("type") == "monitor.diagnostic.result":
                    pending = self.diagnostic_pending
                    if (not self.authorized(session_digest, "monitor.diagnostic.respond")
                        or pending is None or pending[1] is not ws
                        or data.get("nonce") != pending[0] or len(raw) > 1024
                        or time.monotonic() > pending[3]):
                        await ws.close(1008, "Invalid diagnostic response")
                        return
                    card = data.get("card")
                    if (not isinstance(card, (dict, type(None)))
                        or (card is not None and (card.get("repository") != "arthexis/gway-agent-ops"
                        or card.get("badge") not in ("Installed", "Unknown", "Healthy", "Failed", "Updating", "Degraded", "Outdated")
                        or card.get("aria_label") != card.get("badge")))
                        or not re.fullmatch(r"[0-9a-f]{40}", str(data.get("git_sha", "")))
                        or not isinstance(data.get("build_id"), str)
                        or len(data["build_id"]) > 64
                        or data.get("channel") != "deployments"
                        or data.get("visible") is not True):
                        await ws.close(1008, "Invalid diagnostic evidence")
                        return
                    if not pending[2].done():
                        pending[2].set_result(data)
                    continue
                if isinstance(data, dict) and data.get("type") == "monitor.read":
                    if not self.authorized(session_digest, "monitor.read"):
                        await ws.close(1008, "Capability denied")
                        return
                    await ws.send(json.dumps(await self.monitor()))
                    continue
                if isinstance(data, dict) and data.get("type") == "deployment.retry":
                    if not self.authorized(session_digest, "deployment.retry"):
                        await ws.send(json.dumps({"type": "deployment.retry.result", "error": "Permission denied"}))
                        continue
                    name = data.get("name")
                    current = await self.monitor()
                    components = current.get("deployments", {}).get("components", [])
                    matches = [item for item in components if item.get("name") == name]
                    if not isinstance(name, str) or len(matches) != 1:
                        await ws.send(json.dumps({"type": "deployment.retry.result", "name": name, "error": "Unknown component"}))
                        continue
                    item = matches[0]
                    failed = (str(item.get("installation", "")).lower() in ("failed", "error", "failure")
                              or str(item.get("health", "")).lower() in ("failed", "error", "unhealthy", "dead")
                              or bool(item.get("error")))
                    repository = item.get("repository")
                    if not failed or not isinstance(repository, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", repository):
                        await ws.send(json.dumps({"type": "deployment.retry.result", "name": name, "error": "Not an eligible failed deployment"}))
                        continue
                    async with self.deploy_lock:
                        existing = self.deploy_jobs.get(name)
                        if existing is not None and not existing.done():
                            await ws.send(json.dumps({"type": "deployment.retry.running", "name": name}))
                            continue
                        self.deploy_jobs[name] = asyncio.create_task(self.retry_deployment(repository))
                    await ws.send(json.dumps({"type": "deployment.retry.started", "name": name}))
                    continue
                if isinstance(data, dict) and data.get("type") == "deployment.retry.status":
                    name = data.get("name")
                    task = self.deploy_jobs.get(name) if isinstance(name, str) else None
                    if not self.authorized(session_digest, "deployment.retry") or task is None:
                        await ws.send(json.dumps({"type": "deployment.retry.result", "name": name, "error": "No authorized deployment job"}))
                    elif not task.done():
                        await ws.send(json.dumps({"type": "deployment.retry.running", "name": name}))
                    else:
                        await ws.send(json.dumps({"type": "deployment.retry.result", "name": name, **task.result()}))
                    continue
                if not isinstance(data, dict) or data.get("type") != "button.pressed":
                    await ws.close(1008, "Unsupported message")
                    return
                if not self.authorized(session_digest, "button.pressed"):
                    await ws.close(1008, "Capability denied")
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
        finally:
            if self.diagnostic_tv is ws:
                self.diagnostic_tv = None
                self.diagnostic_tv_digest = None
                if self.diagnostic_pending is not None and not self.diagnostic_pending[2].done():
                    self.diagnostic_pending[2].set_result({"type": "monitor.diagnostic.unavailable"})


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
