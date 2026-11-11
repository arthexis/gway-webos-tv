"""Read-only fleet inventory from Watchtower's authenticated MCP node_list.

No credentials are exposed to the TV. If optional private configuration is
absent, the provider reports unavailable rather than treating nodes as offline.
node_list is an enrollment snapshot, NOT the richer future fleet/v1 telemetry.
"""
import json
import os
from pathlib import Path
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit
import urllib.error
import urllib.request

_CACHE = None
_CACHED_AT = 0.0
MAX_RESPONSE = 131072


def _endpoint(url):
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username and not parsed.password
            and parsed.path == "/mcp"
            and not parsed.query and not parsed.fragment
        )
    except ValueError:
        return False


def _read_token(path_string):
    path = Path(path_string)
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise ValueError("unsafe token file")
    token = path.read_text().strip()
    if not token or len(token) > 4096 or any(ord(c) < 33 for c in token):
        raise ValueError("invalid token")
    return token


def _inventory_from_mcp(payload):
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        raise ValueError("invalid RPC response")
    if "error" in payload:
        raise ValueError("MCP error")
    body = payload.get("result")
    if not isinstance(body, dict) or body.get("isError") is True:
        raise ValueError("MCP tool failed")
    if "structuredContent" in body:
        inventory = body["structuredContent"]
    else:
        blocks = body.get("content")
        if not isinstance(blocks, list):
            raise ValueError("missing MCP content")
        inventory = json.loads(next(x["text"] for x in blocks
                                    if isinstance(x, dict) and x.get("type") == "text"))
    if not isinstance(inventory, dict):
        raise ValueError("invalid inventory object")
    if inventory.get("schema") != 1 or inventory.get("source") != "watchtower-enrollment-ledger":
        raise ValueError("unexpected node_list contract")
    rows = inventory.get("nodes")
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("invalid nodes")
    generated = inventory.get("generated_at")
    if not isinstance(generated, str):
        raise ValueError("missing timestamp")
    stamped = datetime.fromisoformat(generated.replace("Z", "+00:00"))
    if stamped.tzinfo is None or not 0 <= (datetime.now(timezone.utc) - stamped).total_seconds() <= 120:
        raise ValueError("stale inventory")
    nodes, seen = [], set()
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("invalid node")
        node = item.get("node")
        # Includes customer nodes such as ocpp-abb-1, not just gway-NNN.
        if not isinstance(node, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", node) or node in seen:
            raise ValueError("unsafe or duplicate node")
        seen.add(node)
        nodes.append({
            "node": node,
            "reachable": item.get("reachable") if item.get("reachable") in ("reachable", "unknown") else "unknown",
            "identity_verified": item.get("identity_verified") is True,
            "observed_at": item.get("observed_at") if isinstance(item.get("observed_at"), str) else None,
            # node_list currently does not provide rich telemetry; never invent it.
            "hardware": {"available": False},
            "services": {"available": False},
            "deployments": {"available": False},
        })
    return {"available": True, "source": "Watchtower MCP node_list",
            "nodes": nodes, "observed_at": generated}


def snapshot():
    global _CACHE, _CACHED_AT
    if _CACHE is not None and time.monotonic() - _CACHED_AT < 60:
        return _CACHE
    url = os.environ.get("GWAY_FLEET_MCP_URL", "")
    token_path = os.environ.get("GWAY_FLEET_TOKEN_FILE", "")
    result = {"available": False, "source": "Watchtower MCP node_list",
              "nodes": [], "error": "Watchtower inventory not configured"}
    if not _endpoint(url) or not token_path:
        return result
    try:
        token = _read_token(token_path)
        request = urllib.request.Request(
            url,
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": "node_list", "arguments": {}}}).encode(),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError("oversized inventory")
        result = _inventory_from_mcp(json.loads(raw))
    except (OSError, ValueError, KeyError, StopIteration, TypeError, urllib.error.URLError):
        result["error"] = "Authenticated Watchtower inventory unavailable"
    if result["available"]:
        _CACHE, _CACHED_AT = result, time.monotonic()
    return result
