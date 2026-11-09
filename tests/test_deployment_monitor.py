from gway_webos_tv import deployment_monitor


def test_deployment_status(monkeypatch):
    monkeypatch.setattr(deployment_monitor, 'read_json', lambda argv: {'checked_at':'now','components':[{'name':'ocpp-csms','installed_sha':'abc','health':'healthy','error':'invalid attempt journal','deployment_evidence':{'repository':'arthexis/ocpp-csms','activated_revision':'abc','installation_state':'activated','runtime_state':'healthy'}}]})
    item = deployment_monitor.snapshot()['components'][0]
    assert item['repository'] == 'arthexis/ocpp-csms'
    assert item['installation'] == 'activated'
    assert item['error'] == 'invalid attempt journal'


def test_unavailable(monkeypatch):
    monkeypatch.setattr(deployment_monitor, 'read_json', lambda argv: None)
    assert deployment_monitor.snapshot()['available'] is False


def test_verified_nonresident_agentops(monkeypatch):
    evidence = {
        'repository': 'arthexis/gway-agent-ops',
        'activated_revision': 'ac1ff877',
        'installation_state': 'activated',
        'runtime_state': 'not_applicable',
        'capabilities': {'runtime_required': False, 'runtime_probe': False},
        'evidence': ['verified_active_release'],
    }
    monkeypatch.setattr(deployment_monitor, 'read_json', lambda argv: {
        'components': [{'name': 'gway-agent-ops', 'deployment_evidence': evidence}]
    })
    item = deployment_monitor.snapshot()['components'][0]
    assert item['installation'] == 'activated'
    assert item['health'] == 'not_applicable'
    assert item['runtime_required'] is False
    assert item['verified_release'] is True


def test_nonresident_without_verified_release_is_not_verified(monkeypatch):
    monkeypatch.setattr(deployment_monitor, 'read_json', lambda argv: {
        'components': [{'name': 'gway-agent-ops', 'deployment_evidence': {
            'installation_state': 'activated', 'runtime_state': 'not_applicable',
            'capabilities': {'runtime_required': False}, 'evidence': []
        }}]
    })
    assert deployment_monitor.snapshot()['components'][0]['verified_release'] is False


def test_bastion_staged_not_activated(monkeypatch):
    sha = 'a' * 40
    monkeypatch.setattr(deployment_monitor, 'read_json', lambda argv: {
        'components': [{'name': 'gway-bastion', 'installed_sha': None,
                        'deployment_evidence': {
                            'repository': 'arthexis/gway-bastion',
                            'installation_state': 'staged',
                            'staged_revision': sha,
                            'activated_revision': None,
                            'runtime_state': 'not_applicable',
                            'evidence': ['verified_staged_release']}}]})
    item = deployment_monitor.snapshot()['components'][0]
    assert item['installation'] == 'staged'
    assert item['staged_revision'] == sha
    assert item['revision'] is None
    assert item['verified_release'] is False
