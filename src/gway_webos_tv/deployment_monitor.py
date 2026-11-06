"""Read-only local deployment evidence for the TV dashboard."""
from .monitor import read_json


def snapshot():
    raw = read_json(['/usr/local/bin/gway-remote', 'status', '--json'])
    if not isinstance(raw, dict) or not isinstance(raw.get('components'), list):
        return {'available': False, 'components': [], 'error': 'Deployment status unavailable'}
    items = []
    for item in raw['components']:
        if not isinstance(item, dict):
            continue
        evidence = item.get('deployment_evidence') or {}
        if not isinstance(evidence, dict):
            evidence = {}
        repo = evidence.get('repository')
        name = item.get('name')
        if not isinstance(name, str):
            continue
        items.append({'name': name, 'repository': repo if isinstance(repo, str) else None,
                      'revision': evidence.get('activated_revision') or item.get('installed_sha'),
                      'installation': evidence.get('installation_state') or item.get('installation') or 'unknown',
                      'health': evidence.get('runtime_state') or item.get('health') or 'unknown',
                      'error': item.get('error') or None})
    return {'available': True, 'node': 'gway-001', 'checked_at': raw.get('checked_at'), 'components': items}
