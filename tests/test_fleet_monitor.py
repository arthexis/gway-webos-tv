import json
from pathlib import Path
from gway_webos_tv import fleet_monitor


def test_unconfigured(monkeypatch):
    monkeypatch.delenv('GWAY_FLEET_MCP_URL', raising=False)
    monkeypatch.delenv('GWAY_FLEET_TOKEN_FILE', raising=False)
    assert fleet_monitor.snapshot()['available'] is False


def test_authenticated_inventory(monkeypatch, tmp_path):
    fleet_monitor._CACHE = None
    token = tmp_path / 'token'
    token.write_text('example-token')
    token.chmod(0o600)
    monkeypatch.setenv('GWAY_FLEET_MCP_URL', 'https://remote.arthexis.com/mcp')
    monkeypatch.setenv('GWAY_FLEET_TOKEN_FILE', str(token))
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit):
            return json.dumps({'result': {'structuredContent': {'source': 'watchtower-enrollment-ledger', 'nodes': [{'node': 'gway-001', 'reachable': 'reachable', 'identity_verified': True, 'observed_at': '2026-11-06T00:00:00Z'}]}}}).encode()
    monkeypatch.setattr(fleet_monitor.urllib.request, 'urlopen', lambda request, timeout: Response())
    result = fleet_monitor.snapshot()
    assert result['available'] is True
    assert result['nodes'][0]['node'] == 'gway-001'
    assert result['nodes'][0]['identity_verified'] is True
    fleet_monitor._CACHE = None
