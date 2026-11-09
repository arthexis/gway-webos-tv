"""Read-only fleet inventory from the authenticated Watchtower MCP endpoint.

The bridge never serves credentials to the TV. Configuration is optional and
must be provisioned separately; unavailable is not equivalent to offline.
"""
import json
import re
from datetime import datetime, timezone
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

_CACHE = None
_CACHED_AT = 0.0


def snapshot():
    global _CACHE, _CACHED_AT
    if _CACHE is not None and time.monotonic() - _CACHED_AT < 60:
        return _CACHE
    url = os.environ.get('GWAY_FLEET_MCP_URL', '')
    token_file = os.environ.get('GWAY_FLEET_TOKEN_FILE', '')
    result = {'available': False, 'source': 'Watchtower MCP fleet_snapshot', 'nodes': [], 'error': 'Watchtower inventory not configured'}
    if not url.startswith('https://') or not url.endswith('/mcp') or not token_file:
        return result
    try:
        path = Path(token_file)
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            raise ValueError('unsafe token file')
        token = path.read_text().strip()
        if not token or len(token) > 4096:
            raise ValueError('invalid token')
        request = urllib.request.Request(url, data=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'fleet_snapshot','arguments':{}}}).encode(), headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json, text/event-stream'}, method='POST')
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read(131073)
        if len(raw) > 131072:
            raise ValueError('oversized inventory')
        data = json.loads(raw)
        body = data.get('result', {})
        if 'structuredContent' in body:
            inventory = body['structuredContent']
        else:
            blocks = body.get('content', [])
            inventory = json.loads(next(x['text'] for x in blocks if x.get('type') == 'text'))
        if inventory.get('schema') != 'gway-remote/fleet/v1' or inventory.get('source') != 'watchtower-enrollment-ledger' or not isinstance(inventory.get('nodes'), list) or len(inventory['nodes']) > 100:
            raise ValueError('invalid inventory')
        generated = inventory.get('generated_at')
        if not isinstance(generated, str):
            raise ValueError('missing fleet timestamp')
        timestamp = datetime.fromisoformat(generated.replace('Z', '+00:00'))
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()
        if timestamp.tzinfo is None or not 0 <= age <= 120:
            raise ValueError('stale fleet snapshot')
        nodes = []
        seen = set()
        for row in inventory['nodes']:
            if not isinstance(row, dict) or not isinstance(row.get('node'), str) or not re.fullmatch(r'gway-[0-9]+', row['node']) or row['node'] in seen:
                raise ValueError('invalid fleet node')
            seen.add(row['node'])
            nodes.append({'node': row['node'][:64], 'reachable': row.get('reachable') if row.get('reachable') in ('reachable','unknown') else 'unknown', 'identity_verified': row.get('identity_verified') is True, 'observed_at': row.get('observed_at') if isinstance(row.get('observed_at'), str) else None, 'hardware': row.get('hardware') if inventory.get('schema') == 'gway-remote/fleet/v1' and isinstance(row.get('hardware'), dict) else {'available': False}, 'services': row.get('services') if inventory.get('schema') == 'gway-remote/fleet/v1' and isinstance(row.get('services'), dict) else {'available': False}, 'deployments': row.get('deployments') if inventory.get('schema') == 'gway-remote/fleet/v1' and isinstance(row.get('deployments'), dict) else {'available': False}})
        result = {'available': True, 'source': 'Watchtower MCP node_list', 'nodes': nodes, 'observed_at': inventory.get('generated_at')}
    except (OSError, ValueError, KeyError, StopIteration, TypeError, urllib.error.URLError):
        result['error'] = 'Authenticated Watchtower inventory unavailable'
    if result['available']:
        _CACHE, _CACHED_AT = result, time.monotonic()
    return result
