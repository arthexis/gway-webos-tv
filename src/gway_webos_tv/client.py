"""Small bscpylgtv adapter for bounded, one-shot GWAY operations."""

import asyncio
import hashlib
import ipaddress
import logging
import re
import socket
import ssl
from dataclasses import dataclass

from bscpylgtv import WebOsClient

from .state import Device, TVError

# Third-party exceptions may contain protocol payloads. The CLI emits only its own errors.
logging.getLogger("bscpylgtv.webos_client").setLevel(logging.CRITICAL)


def validate_host(host: str) -> str:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host):
            raise TVError("Use a TV IP address or hostname, without a URL or port.") from None
    return host


def url_host(host: str) -> str:
    return f"[{host}]" if ":" in host else host


@dataclass
class Peer:
    fingerprint: str
    ip: str
    context: ssl.SSLContext


def inspect_peer(host: str, port: int, fingerprint: str | None, timeout: float) -> Peer:
    """Check the saved pin before sending a key, then pin the actual SDK connection too."""
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=host) as stream:
                certificate = stream.getpeercert(binary_form=True)
                peer_ip = stream.getpeername()[0]
    except OSError:
        raise TVError("Cannot establish a TLS connection to the TV.") from None
    digest = hashlib.sha256(certificate).hexdigest()
    if fingerprint and digest != fingerprint:
        raise TVError("TV certificate changed; no pairing key was sent.")
    pinned = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    pinned.check_hostname = False  # TV certificates do not contain the LAN IP.
    pinned.verify_mode = ssl.CERT_REQUIRED
    pinned.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
    pinned.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(certificate))
    return Peer(digest, peer_ip, pinned)


class MemoryStorage:
    """Keep the SDK from creating its default SQLite file in the working directory."""

    async def get_key(self, key):
        return None

    async def set_key(self, key, value):
        pass

    async def list_keys(self):
        return {}


class TV:
    def __init__(self, device: Device, timeout: float = 10, port: int = 3001):
        self.device = device
        self.timeout = timeout
        self.port = port
        self.client = None
        self.peer = None

    async def connect(self, *, pair: bool = False) -> dict:
        if not pair and not self.device.client_key:
            raise TVError("Normal commands require saved pairing; run pair first.")
        host = validate_host(self.device.host)
        self.peer = await asyncio.to_thread(
            inspect_peer, host, self.port, self.device.fingerprint, self.timeout
        )
        self.client = await WebOsClient.create(
            url_host(host),
            client_key=self.device.client_key,
            storage=MemoryStorage(),
            states=[],
            connect_retry_attempts=1,
            timeout_connect=max(1, int(self.timeout)),
            ping_interval=None,
            get_hello_info=True,
            pairing_type="PROMPT",
        )
        self.client.port = self.port
        self.client.manifest = self.device.manifest
        # bscpylgtv 0.5.x exposes no SSL-context argument. This is the sole private
        # adapter hook; loopback TLS tests cover it and the supported version is bounded.
        self.client._ssl_context = self.peer.context
        await self.call(self.client.connect(), timeout=120 if pair else self.timeout)
        info = await self.call(self.client.get_system_info())
        if not isinstance(info, dict) or not isinstance(info.get("modelName"), str):
            raise TVError("The endpoint did not identify a webOS TV model.")
        model = info["modelName"]
        if self.device.model and self.device.model != model:
            raise TVError("TV model differs from the saved device; no control command was sent.")
        self.device.model = model
        self.device.fingerprint = self.peer.fingerprint
        self.device.client_key = self.client.client_key
        return info

    async def close(self):
        if self.client is not None:
            try:
                await asyncio.wait_for(self.client.disconnect(), timeout=5)
            except Exception:
                pass

    async def call(self, operation, *, timeout: float | None = None):
        try:
            return await asyncio.wait_for(operation, timeout=timeout or self.timeout)
        except TimeoutError:
            raise TVError("TV operation timed out.") from None
        except TVError:
            raise
        except Exception as error:
            # Never print SDK exception bodies: they can contain keys or capture URLs.
            if "401" in str(error):
                raise TVError("TV denied permission; pair with the required permissions.") from None
            if "404" in str(error):
                raise TVError("This TV does not support the requested API method.") from None
            raise TVError("TV connection or command failed.") from None

    async def status(self) -> dict:
        app = await self.call(self.client.get_current_app())
        inputs = await self.inputs()
        current = next((x for x in inputs if x.get("app_id") == app), None)
        return {
            "host": self.device.host,
            "model": self.device.model,
            "connected": True,
            "paired": True,
            "foreground_app": app,
            "input": current,
        }

    async def inputs(self) -> list[dict]:
        devices = await self.call(self.client.get_inputs())
        return [
            {
                "id": item.get("id"),
                "label": item.get("label"),
                "connected": item.get("connected"),
                "app_id": item.get("appId"),
            }
            for item in devices or []
        ]

    async def wait_foreground(self, expected: str, wait: float) -> str:
        deadline = asyncio.get_running_loop().time() + wait
        while True:
            current = await self.call(self.client.get_current_app())
            if current == expected:
                return current
            if asyncio.get_running_loop().time() >= deadline:
                raise TVError(
                    "TV accepted the command, but the foreground change was not confirmed."
                )
            await asyncio.sleep(0.5)

    async def hdmi(self, number: int, wait: float) -> dict:
        target = next((x for x in await self.inputs() if x["id"] == f"HDMI_{number}"), None)
        if not target or not target["app_id"]:
            raise TVError(f"HDMI {number} is not available on this TV.")
        await self.call(self.client.set_input(target["id"]))
        app = await self.wait_foreground(target["app_id"], wait)
        return {
            "input": target["id"],
            "label": target["label"],
            "foreground_app": app,
            "verified": True,
        }

    async def apps(self) -> list[dict]:
        apps = await self.call(self.client.get_apps_all())
        return [{"id": x.get("id"), "title": x.get("title")} for x in apps or []]

    async def launch(self, app: str, wait: float) -> dict:
        await self.call(self.client.launch_app(app))
        foreground = await self.wait_foreground(app, wait)
        return {"app_id": app, "foreground_app": foreground, "verified": True}
