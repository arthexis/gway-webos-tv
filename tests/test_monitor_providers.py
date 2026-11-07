"""Provider registry compatibility and failure isolation."""
from unittest.mock import patch

from gway_webos_tv.monitor import PROVIDERS, collect_providers


def test_provider_registry_namespaces():
    assert PROVIDERS == ("github", "deployments", "fleet")
    with (
        patch("gway_webos_tv.github_prs.snapshot", return_value={"pull_requests": []}),
        patch("gway_webos_tv.deployment_monitor.snapshot", return_value={"available": True}),
        patch("gway_webos_tv.fleet_monitor.snapshot", return_value={"available": False}),
    ):
        result = collect_providers()
    assert tuple(result) == PROVIDERS
    assert result["github"]["pull_requests"] == []
    assert result["deployments"]["available"] is True


def test_failed_provider_does_not_block_others():
    with (
        patch("gway_webos_tv.github_prs.snapshot", side_effect=ValueError("private details")),
        patch("gway_webos_tv.deployment_monitor.snapshot", return_value={"available": True}),
        patch("gway_webos_tv.fleet_monitor.snapshot", return_value={"available": True}),
    ):
        result = collect_providers()
    assert result["github"] == {"available": False, "error": "Provider unavailable"}
    assert result["deployments"]["available"] is True
    assert result["fleet"]["available"] is True
    assert "private details" not in str(result)
