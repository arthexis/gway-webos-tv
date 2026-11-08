"""Federated MCP stdio provider; Watchtower owns authenticated transport and scopes.

The node publishes exactly two tools. No arbitrary command, pairing or shell API.
Deployment registration is owned by gway-remote's existing federation machinery.
"""

import asyncio
import json
import sys
from pathlib import Path

from .client import TV
from .dispatcher import Operation, dispatch
from .images import save_image
from .state import TVError, load_state

MAX_MESSAGE = 65536
READ = frozenset({"status", "inputs.list", "apps.list"})
EXECUTE = frozenset({"inputs.select", "apps.launch", "screen.capture", "youtube.open", "youtube.search"})
TOOLS = (
    {"name": "read", "description": "Read webOS TV status, inputs or installed applications.",
     "inputSchema": {"type": "object", "properties": {"operation": {"type": "string", "enum": sorted(READ)}},
                     "required": ["operation"], "additionalProperties": False},
     "annotations": {"readOnlyHint": True}, "required_scope": "gway:remote"},
    {"name": "execute", "description": "Execute a validated webOS TV action; requires gway:execute.",
     "inputSchema": {"type": "object", "properties": {
         "operation": {"type": "string", "enum": sorted(EXECUTE)},
         "number": {"type": "integer", "minimum": 1, "maximum": 8},
         "app_id": {"type": "string", "minLength": 1, "maxLength": 256},
         "wait": {"type": "number", "exclusiveMinimum": 0, "maximum": 120},
         "query": {"type": "string", "minLength": 1, "maxLength": 120},
         "output": {"type": "string", "minLength": 1, "maxLength": 512}},
         "required": ["operation"], "additionalProperties": False},
     "annotations": {"readOnlyHint": False}, "required_scope": "gway:execute"},
)


def validate(name, arguments):
    if name not in ("read", "execute") or type(arguments) is not dict:
        raise ValueError("invalid_tool")
    operation = arguments.get("operation")
    allowed = READ if name == "read" else EXECUTE
    if type(operation) is not str or operation not in allowed:
        raise ValueError("operation_not_allowed")
    expected = {
        "status": set(), "inputs.list": set(), "apps.list": set(),
        "inputs.select": {"number", "wait"}, "apps.launch": {"app_id", "wait"},
        "screen.capture": {"output"}, "youtube.open": {"wait"},
        "youtube.search": {"query", "wait"},
    }[operation]
    supplied = set(arguments) - {"operation"}
    if not supplied <= expected:
        raise ValueError("invalid_arguments")
    params = {key: value for key, value in arguments.items() if key != "operation"}
    if operation == "inputs.select":
        if type(params.get("number")) is not int or not 1 <= params["number"] <= 8:
            raise ValueError("invalid_arguments")
    if operation == "apps.launch":
        app = params.get("app_id")
        if type(app) is not str or not 1 <= len(app) <= 256 or any(ord(ch) < 32 for ch in app):
            raise ValueError("invalid_arguments")
    if "wait" in expected:
        wait = params.get("wait", 30)
        if type(wait) not in (int, float) or not 0 < wait <= 120:
            raise ValueError("invalid_arguments")
        params["wait"] = wait
    if operation == "youtube.search":
        query = params.get("query")
        if type(query) is not str or not 1 <= len(query) <= 120:
            raise ValueError("invalid_arguments")
    if "output" in params:
        output = params["output"]
        if type(output) is not str or not 1 <= len(output) <= 512 or any(ord(ch) < 32 for ch in output):
            raise ValueError("invalid_arguments")
        params["output"] = Path(output)
    return Operation(operation, params)


async def execute_operation(operation):
    """Use saved pairing only; never silently pair or override the TV host."""
    from .state import default_state_path
    device = load_state(default_state_path(), required=True)
    tv = TV(device, timeout=10)
    try:
        await tv.connect(pair=False)
        youtube_factory = None
        if operation.name.startswith("youtube."):
            from .youtube import YouTube, validate_query
            if operation.name == "youtube.search":
                operation.params["query"] = validate_query(operation.params["query"])
            YouTube.check_dependencies()
            youtube_factory = YouTube
        return await dispatch(tv, operation, save_capture=save_image, youtube_factory=youtube_factory)
    finally:
        await tv.close()


def call_tool(name, arguments):
    operation = validate(name, arguments)
    return asyncio.run(execute_operation(operation))


def handle(request):
    if type(request) is not dict or request.get("jsonrpc") != "2.0":
        raise ValueError("invalid_request")
    method = request.get("method")
    if method == "notifications/initialized":
        return None
    if "id" not in request:
        raise ValueError("invalid_request")
    if method == "initialize":
        result = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "gway-webos-tv", "version": "1"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        # Gateway classifies by annotations and enforces OAuth before forwarding.
        result = {"tools": [{key: val for key, val in tool.items() if key != "required_scope"} for tool in TOOLS]}
    elif method == "tools/call":
        params = request.get("params")
        if type(params) is not dict or type(params.get("name")) is not str:
            raise ValueError("invalid_arguments")
        try:
            data = call_tool(params["name"], params.get("arguments", {}))
            result = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}
        except (ValueError, TVError, OSError, RuntimeError) as exc:
            code = str(exc) if type(exc) is ValueError and str(exc) in {
                "invalid_tool", "operation_not_allowed", "invalid_arguments"} else "provider_unavailable"
            result = {"content": [{"type": "text", "text": json.dumps({"error": code})}], "isError": True}
    else:
        raise ValueError("method_not_found")
    return {"jsonrpc": "2.0", "id": request["id"], "result": result}


def main():
    for raw in sys.stdin.buffer:
        if len(raw) > MAX_MESSAGE:
            continue
        try:
            reply = handle(json.loads(raw))
        except (ValueError, TypeError, UnicodeError):
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
        if reply is not None:
            encoded = json.dumps(reply, ensure_ascii=False, separators=(",", ":"))
            if len(encoded.encode("utf-8")) > MAX_MESSAGE:
                encoded = json.dumps({"jsonrpc": "2.0", "id": reply.get("id"),
                                      "error": {"code": -32603, "message": "Response too large"}})
            sys.stdout.write(encoded + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
