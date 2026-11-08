"""Offline contract tests for the two federated MCP tools."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gway_webos_tv import mcp_stdio as mcp
from gway_webos_tv.dispatcher import Operation


def test_catalog_exactly_two_tools_and_scopes():
    assert [tool["name"] for tool in mcp.TOOLS] == ["read", "execute"]
    assert [tool["required_scope"] for tool in mcp.TOOLS] == ["gway:read", "gway:execute"]
    response = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = response["result"]["tools"]
    assert [tool["name"] for tool in tools] == ["read", "execute"]
    assert tools[0]["annotations"]["readOnlyHint"] is True
    assert tools[1]["annotations"]["readOnlyHint"] is False


@pytest.mark.parametrize(("tool", "args"), [
    ("read", {"operation": "pair"}),
    ("execute", {"operation": "pair.code"}),
    ("execute", {"operation": "status"}),
    ("read", {"operation": "inputs.select", "number": 1}),
    ("execute", {"operation": "shell", "command": "id"}),
    ("execute", {"operation": "apps.launch", "app_id": "browser", "command": "id"}),
    ("execute", {"operation": "inputs.select", "number": True}),
    ("execute", {"operation": "inputs.select", "number": 9}),
    ("execute", {"operation": "apps.launch", "app_id": ""}),
    ("execute", {"operation": "youtube.search", "query": ""}),
    ("execute", {"operation": "youtube.open", "wait": 0}),
    ("execute", {"operation": "screen.capture", "output": "unsafe.jpg"}),
])
def test_negative_authorization_and_schema(tool, args):
    with pytest.raises(ValueError):
        mcp.validate(tool, args)


@pytest.mark.parametrize(("tool", "args", "name"), [
    ("read", {"operation": "status"}, "status"),
    ("read", {"operation": "inputs.list"}, "inputs.list"),
    ("read", {"operation": "apps.list"}, "apps.list"),
    ("execute", {"operation": "inputs.select", "number": 2}, "inputs.select"),
    ("execute", {"operation": "apps.launch", "app_id": "browser"}, "apps.launch"),
    ("execute", {"operation": "screen.capture"}, "screen.capture"),
    ("execute", {"operation": "youtube.open"}, "youtube.open"),
    ("execute", {"operation": "youtube.search", "query": "openai"}, "youtube.search"),
])
def test_operation_parity(tool, args, name):
    operation = mcp.validate(tool, args)
    assert isinstance(operation, Operation)
    assert operation.name == name


def test_jsonrpc_parity_and_no_tv_on_rejection():
    with patch.object(mcp, "execute_operation", new_callable=AsyncMock) as execute:
        response = mcp.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                               "params": {"name": "execute", "arguments": {"operation": "pair"}}})
        assert response["result"]["isError"] is True
        assert json.loads(response["result"]["content"][0]["text"]) == {"error": "operation_not_allowed"}
        execute.assert_not_awaited()


def test_structured_result_uses_shared_dispatcher():
    tv = MagicMock()
    tv.status = AsyncMock(return_value={"model": "test"})
    from gway_webos_tv.dispatcher import dispatch
    op = mcp.validate("read", {"operation": "status"})
    assert asyncio.run(dispatch(tv, op)) == {"model": "test"}
