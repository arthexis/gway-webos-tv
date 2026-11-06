#!/usr/bin/env python3
"""Issue a TV pairing code through the dedicated WireGuard admin channel."""

import base64
import hashlib
import json
import os
import secrets
import socket
import ssl
import stat
import struct
import sys
from pathlib import Path


def read_exact(sock, length):
    data = b""
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise RuntimeError("Bridge closed the connection")
        data += chunk
    return data


def main():
    if not sys.stdout.isatty():
        raise RuntimeError("Run in a private terminal; output redirection is disabled")
    base = Path.home() / ".config/gway-webos-tv"
    config = json.loads((base / "pair-admin.json").read_text())
    key_path = base / "pair-admin.key"
    with key_path.open() as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RuntimeError("Pairing administrator key has unsafe ownership or permissions")
        credential = stream.read().strip()
    code = f"{secrets.randbelow(1000000):06d}"
    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + code).encode()).hexdigest()
    context = ssl.create_default_context(cafile=config["ca_file"])
    with socket.create_connection((config["address"], config["port"]), timeout=10) as raw:
        with context.wrap_socket(raw, server_hostname=config["server_name"]) as sock:
            nonce = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
            request = (
                "GET /admin/pair HTTP/1.1\r\nHost: "
                + config["server_name"]
                + "\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: "
                + nonce
                + "\r\n\r\n"
            )
            sock.sendall(request.encode("ascii"))
            header = b""
            while not header.endswith(b"\r\n\r\n") and len(header) < 16384:
                header += read_exact(sock, 1)
            lines = header.decode("iso-8859-1").split("\r\n")
            fields = dict(line.split(":", 1) for line in lines[1:] if ":" in line)
            fields = {key.lower(): value.strip() for key, value in fields.items()}
            expected = base64.b64encode(
                hashlib.sha1((nonce + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
            ).decode()
            if " 101 " not in lines[0] or fields.get("sec-websocket-accept") != expected:
                raise RuntimeError("Bridge WebSocket upgrade failed")
            payload = json.dumps(
                {
                    "type": "admin.arm_pairing",
                    "credential": credential,
                    "salt": salt,
                    "sha256": digest,
                }
            ).encode()
            mask = secrets.token_bytes(4)
            if len(payload) > 65535:
                raise RuntimeError("Invalid admin request")
            length = (
                bytes([0x80 | len(payload)])
                if len(payload) < 126
                else bytes([0x80 | 126]) + struct.pack("!H", len(payload))
            )
            sock.sendall(
                b"\x81"
                + length
                + mask
                + bytes(value ^ mask[i % 4] for i, value in enumerate(payload))
            )
            first, second = read_exact(sock, 2)
            size = second & 0x7F
            if (first & 0x0F) != 1 or second & 0x80 or size > 125:
                raise RuntimeError("Bridge rejected the request")
            response = json.loads(read_exact(sock, size))
            if response.get("type") != "pairing.open":
                raise RuntimeError("Bridge did not open pairing")
    print("Enter this code on the TV within two minutes:", code, flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print("Cannot open pairing window:", type(error).__name__, file=sys.stderr)
        sys.exit(1)
