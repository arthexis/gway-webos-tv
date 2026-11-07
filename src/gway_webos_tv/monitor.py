"""Read-only monitor snapshots assembled from registered providers."""

import json
import subprocess
import time
from datetime import datetime, timezone

from .monitor_sources import hardware_snapshot, ocpp_snapshot


def read_json(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=12, check=True)
        data = json.loads(result.stdout)
        return data if isinstance(data, (dict, list)) else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


PROVIDERS = ("hardware", "ocpp", "github", "deployments", "fleet")


def provider_registry():
    """Resolve collectors at call time so existing test patching still works."""
    from .github_prs import snapshot as github_snapshot
    from .deployment_monitor import snapshot as deployment_snapshot
    from .fleet_monitor import snapshot as fleet_snapshot

    return {
        "hardware": lambda: hardware_snapshot(read_json),
        "ocpp": lambda: ocpp_snapshot(read_json),
        "github": github_snapshot,
        "deployments": deployment_snapshot,
        "fleet": fleet_snapshot,
    }


def collect_providers(collectors=None, metrics=None):
    """Collect every namespace independently; metrics remain server-side."""
    collectors = provider_registry() if collectors is None else collectors
    if len(set(collectors)) != len(collectors) or not collectors:
        raise ValueError("Invalid provider registry")
    results = {}
    for name, collect in collectors.items():
        if not isinstance(name, str) or not name or not name.replace("-", "").isalnum():
            raise ValueError("Invalid provider identifier")
        if not callable(collect):
            raise ValueError("Provider must be callable")
        started = time.monotonic()
        try:
            results[name] = collect()
        except Exception:
            results[name] = {"available": False, "error": "Provider unavailable"}
        finally:
            if metrics is not None:
                metrics[name] = time.monotonic() - started
    return results


def snapshot():
    providers = collect_providers()
    return {
        "type": "monitor.snapshot",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        **providers,
    }
