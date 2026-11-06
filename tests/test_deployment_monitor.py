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
