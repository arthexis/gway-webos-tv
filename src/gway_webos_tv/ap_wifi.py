"""Current wlan0 AP join details for the already-paired webOS Monitor only.

Never save credentials, emit them in standard monitor snapshots, or log nmcli
stdout/stderr. Every request re-reads the active AP profile, including its key.
"""
from __future__ import annotations

import ipaddress
import json
import re
import subprocess

import qrcode


UUID = re.compile(r"^[0-9a-fA-F-]{36}$")


class WifiUnavailable(ValueError):
    pass


def wifi_escape(value: str) -> str:
    """Escape the special characters in the WIFI: QR payload format."""
    return "".join("\\" + char if char in '\\;,:"' else char for char in value)


def qr_matrix(ssid: str, password: str, *, hidden: bool = False) -> list[str]:
    payload = (
        "WIFI:T:WPA;S:" + wifi_escape(ssid)
        + ";P:" + wifi_escape(password)
        + (";H:true" if hidden else "") + ";;"
    )
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1, border=4
    )
    qr.add_data(payload)
    qr.make(fit=True)
    rows = ["".join("1" if cell else "0" for cell in row) for row in qr.get_matrix()]
    if not 21 <= len(rows) <= 185 or any(len(row) != len(rows) for row in rows):
        raise WifiUnavailable("Invalid Wi-Fi QR")
    return rows


def command(*args: str) -> str:
    result = subprocess.run(
        list(args), capture_output=True, text=True, check=True, timeout=5
    )
    # Preserve spaces that may be part of an actual SSID or key.
    return result.stdout.rstrip("\r\n")


def current_ap(reader=command) -> dict:
    """Only active NetworkManager wlan0/AP, never the uplink's PSK.

    The returned object is sensitive. Send only to the paired Gway Monitor
    in the separate monitor.wifi message; never persist or cache it.
    """
    try:
        profile = reader(
            "nmcli", "--escape", "no", "-g", "GENERAL.CON-UUID",
            "device", "show", "wlan0",
        )
        if not UUID.fullmatch(profile):
            raise WifiUnavailable("No active AP profile")
        def field(key: str, *, secret: bool = False) -> str:
            args = ["nmcli"]
            if secret:
                args.append("--show-secrets")
            args.extend(("--escape", "no", "-g", key, "connection", "show", profile))
            return reader(*args)
        if field("802-11-wireless.mode") != "ap":
            raise WifiUnavailable("wlan0 is not an AP")
        ssid = field("802-11-wireless.ssid")
        auth = field("802-11-wireless-security.key-mgmt")
        password = field("802-11-wireless-security.psk", secret=True)
        if not (ssid and len(ssid.encode("utf-8")) <= 32 and
                not any(ord(c) < 32 for c in ssid) and
                auth in ("wpa-psk", "sae") and
                8 <= len(password) <= 63 and
                password != "********" and
                not any(ord(c) < 32 or ord(c) > 126 for c in password)):
            raise WifiUnavailable("AP key unavailable or unsupported")

        data = json.loads(reader("ip", "-4", "-j", "address", "show", "dev", "wlan0"))
        if not isinstance(data, list) or len(data) != 1:
            raise WifiUnavailable("AP address unavailable")
        candidates = [
            row for row in data[0].get("addr_info", [])
            if isinstance(row, dict) and row.get("family") == "inet"
            and row.get("scope") == "global"
        ]
        if len(candidates) != 1:
            raise WifiUnavailable("AP address ambiguous")
        address = ipaddress.ip_interface(
            str(candidates[0]["local"]) + "/" + str(candidates[0]["prefixlen"])
        )
        if not address.ip.is_private:
            raise WifiUnavailable("AP gateway is not private")
        return {
            "available": True,
            "ssid": ssid,
            "security": "WPA3" if auth == "sae" else "WPA2",
            "password": password,
            "gateway": str(address.ip),
            "subnet": str(address.network),
            "portal_url": "http://" + str(address.ip),
            "qr": qr_matrix(ssid, password),
        }
    except (WifiUnavailable, OSError, ValueError, KeyError, TypeError,
            subprocess.SubprocessError, UnicodeError):
        # No exception details: stderr / config values may contain credentials.
        return {"available": False}


def wifi_message() -> dict:
    return {"type": "monitor.wifi", "wifi": current_ap()}
