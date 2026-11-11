"""Offline contract tests against actual Watchtower node_list envelope."""
from datetime import datetime, timezone, timedelta
import json

import pytest
from gway_webos_tv import fleet_monitor


@pytest.fixture(autouse=True)
def reset_cache():
    fleet_monitor._CACHE = None
    yield
    fleet_monitor._CACHE = None


def configured(monkeypatch, tmp_path, payload):
    token = tmp_path / "token"
    token.write_text("example-token")
    token.chmod(0o600)
    monkeypatch.setenv("GWAY_FLEET_MCP_URL", "https://watchtower.example/mcp")
    monkeypatch.setenv("GWAY_FLEET_TOKEN_FILE", str(token))
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            return json.dumps(payload).encode()

    def fake_urlopen(request, timeout):
        calls.append(json.loads(request.data))
        assert timeout == 5
        assert request.full_url == "https://watchtower.example/mcp"
        return Response()

    monkeypatch.setattr(fleet_monitor.urllib.request, "urlopen", fake_urlopen)
    return calls, token


def envelope(node_list, structured=True):
    body = ({"structuredContent": node_list} if structured else
            {"content": [{"type": "text", "text": json.dumps(node_list)}]})
    return {"jsonrpc": "2.0", "id": 1, "result": body}


def inventory(**overrides):
    data = {"schema": 1, "source": "watchtower-enrollment-ledger",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "nodes": [
                {"node": "gway-001", "reachable": "reachable", "identity_verified": True,
                 "observed_at": "2026-11-11T09:00:00Z"},
                {"node": "ocpp-abb-1", "reachable": "unknown", "identity_verified": False,
                 "observed_at": None},
            ]}
    data.update(overrides)
    return data


def test_unconfigured(monkeypatch):
    monkeypatch.delenv("GWAY_FLEET_MCP_URL", raising=False)
    monkeypatch.delenv("GWAY_FLEET_TOKEN_FILE", raising=False)
    assert fleet_monitor.snapshot()["available"] is False


@pytest.mark.parametrize("structured", [True, False])
def test_live_node_list_contract_and_unknown_telemetry(monkeypatch, tmp_path, structured):
    calls, _ = configured(monkeypatch, tmp_path, envelope(inventory(), structured))
    result = fleet_monitor.snapshot()
    assert result["available"] is True
    assert len(result["nodes"]) == 2
    assert result["nodes"][1]["node"] == "ocpp-abb-1"
    assert result["nodes"][0]["identity_verified"] is True
    assert result["nodes"][1]["identity_verified"] is False
    for row in result["nodes"]:
        assert row["hardware"] == {"available": False}
        assert row["services"] == {"available": False}
        assert row["deployments"] == {"available": False}
    assert calls == [{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": "node_list", "arguments": {}}}]
    assert fleet_monitor.snapshot() == result  # Cache without new request.
    assert len(calls) == 1


@pytest.mark.parametrize("bad", [
    {"schema": "gway-remote/fleet/v1"},
    {"source": "unknown"},
    {"nodes": [{"node": "gway-001"}, {"node": "gway-001"}]},
    {"nodes": [{"node": "../../secret"}]},
    {"generated_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()},
])
def test_bad_or_stale_inventory_fails_closed(monkeypatch, tmp_path, bad):
    configured(monkeypatch, tmp_path, envelope(inventory(**bad)))
    assert fleet_monitor.snapshot()["available"] is False


def test_provider_error_fails_closed(monkeypatch, tmp_path):
    configured(monkeypatch, tmp_path, {"jsonrpc": "2.0", "id": 1, "result": {
        "isError": True, "content": [{"type": "text", "text": "{}"}]}})
    assert fleet_monitor.snapshot()["available"] is False


def test_private_token_file_is_required(monkeypatch, tmp_path):
    calls, token = configured(monkeypatch, tmp_path, envelope(inventory()))
    token.chmod(0o644)
    assert fleet_monitor.snapshot()["available"] is False
    assert calls == []


def test_url_with_credentials_is_rejected(monkeypatch, tmp_path):
    calls, _ = configured(monkeypatch, tmp_path, envelope(inventory()))
    monkeypatch.setenv("GWAY_FLEET_MCP_URL", "https://user:password@watchtower.example/mcp")
    assert fleet_monitor.snapshot()["available"] is False
    assert calls == []
