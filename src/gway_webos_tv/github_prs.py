"""Read-only GitHub PR summaries for TV."""
import json
import subprocess
import time
from datetime import datetime, timezone

REPOS = ('arthexis/gway-remote', 'arthexis/ocpp-csms', 'arthexis/ocpp-reports', 'arthexis/gway-webos-tv', 'arthexis/gway-agent-ops', 'arthexis/gway-rfid', 'arthexis/gway-lcd-sound', 'arthexis/gway-lcd', 'arthexis/gway-sound', 'arthexis/ocpp-simulator')


_cache = None
_cache_at = 0.0

def snapshot():
    global _cache, _cache_at
    if _cache is not None and time.monotonic() - _cache_at < 120:
        return _cache
    prs, errors = [], []
    for repo in REPOS:
        try:
            raw = subprocess.run(['gh', 'pr', 'list', '-R', repo, '--state', 'open', '--limit', '100', '--json', 'number,title,isDraft,mergeStateStatus,statusCheckRollup'], capture_output=True, text=True, timeout=5, check=True)
            for item in json.loads(raw.stdout):
                checks = item.get('statusCheckRollup') or []
                states = [c.get('conclusion') or c.get('state') or c.get('status') for c in checks if isinstance(c, dict)]
                ci = 'failed' if any(x in ('FAILURE','ERROR','TIMED_OUT','CANCELLED') for x in states) else 'pending' if any(x in ('PENDING','IN_PROGRESS','QUEUED','WAITING','REQUESTED') for x in states) else 'passed' if states else 'unknown'
                prs.append({'repo': repo, 'number': item['number'], 'title': item['title'][:160], 'draft': item.get('isDraft', False), 'merge': item.get('mergeStateStatus'), 'ci': ci})
        except (OSError, ValueError, subprocess.SubprocessError, KeyError, TypeError):
            errors.append(repo)
    _cache = {'repositories': list(REPOS), 'pull_requests': prs[:200], 'errors': errors, 'observed_at': datetime.now(timezone.utc).isoformat()}
    _cache_at = time.monotonic()
    return _cache
