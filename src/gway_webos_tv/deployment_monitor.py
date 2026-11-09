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
        # A status observation is not a deployment event. Only use a
        # dedicated activation/deployment timestamp if explicitly supplied.
        deployed_at = next((evidence[key] for key in
                            ('activated_at', 'deployed_at', 'deployment_at')
                            if isinstance(evidence.get(key), str) and evidence[key]), None)
        items.append({'name': name, 'repository': repo if isinstance(repo, str) else None,
                      'revision': evidence.get('activated_revision') or item.get('installed_sha'),
                      'staged_revision': evidence.get('staged_revision') if name == 'gway-bastion' else None,
                      'installation': evidence.get('installation_state') or item.get('installation') or 'unknown',
                      'health': evidence.get('runtime_state') or item.get('health') or 'unknown',
                      'deployed_at': deployed_at, 'error': item.get('error') or None,
                      'runtime_required': (evidence.get('capabilities') or {}).get('runtime_required') if isinstance(evidence.get('capabilities'), dict) else None,
                      'verified_release': 'verified_active_release' in evidence.get('evidence', []) if isinstance(evidence.get('evidence'), list) else False})
    return {'available': True, 'node': 'gway-001', 'checked_at': raw.get('checked_at'), 'components': items}
