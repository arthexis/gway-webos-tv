"""Retry operation is scoped, validates inventory and never runs arbitrary TV input."""
import asyncio
from unittest.mock import patch

from gway_webos_tv.event_bridge import Bridge


def test_retry_command_is_bounded_and_uses_repository(tmp_path):
    bridge = Bridge(tmp_path)
    class Completed:
        returncode = 0
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return Completed()
    with patch("gway_webos_tv.event_bridge.subprocess.run", side_effect=run):
        result = asyncio.run(bridge.retry_deployment("arthexis/ocpp-csms"))
    assert result == {"success": True, "error": None}
    assert calls[0][0] == ["/usr/local/bin/gway-remote", "deploy", "arthexis/ocpp-csms", "--follow"]
    assert calls[0][1]["timeout"] == 900


def test_retry_failure_is_reported(tmp_path):
    bridge = Bridge(tmp_path)
    class Completed:
        returncode = 1
    with patch("gway_webos_tv.event_bridge.subprocess.run", return_value=Completed()):
        result = asyncio.run(bridge.retry_deployment("arthexis/ocpp-csms"))
    assert result["success"] is False
    assert result["error"]
