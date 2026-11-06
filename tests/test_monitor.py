"""Regression checks for the read-only monitor snapshot contract."""

from unittest.mock import patch

from gway_webos_tv.monitor import snapshot


def test_monitor_snapshot_with_populated_data():
    hardware = {
        "host": {
            "model": "Raspberry Pi",
            "cpu_temperature_c": 47.5,
            "uptime_seconds": 3600,
            "memory": {"used_bytes": 1024},
            "root_filesystem": {"free_bytes": 2048},
        },
        "ambient_temperature": {"celsius": 24.5},
    }
    network = {"schema": "gway-remote/network/v1", "interfaces": {
        "eth0": {"present": True, "up": True, "ipv4": ["192.0.2.10"]},
        "wlan0": {"present": True, "up": False, "ipv4": []},
        "wlan1": {"present": False, "up": False, "ipv4": []},
    }}
    status = {"schema": "ocpp-csms/status/v1", "data": {
        "server": "running", "chargers": [
            {"id": "charger-a", "connected": True},
            {"id": "charger-b", "connected": False},
        ]
    }}
    active = {"schema": "ocpp-csms/transactions/v1", "data": {"transactions": [
        {"id": 42, "charger_id": "charger-a", "connector_id": 1,
         "state": "active", "energy_wh": 1250}
    ]}}
    last = {"schema": "ocpp-csms/transactions/v1", "data": {"transactions": []}}
    with patch("gway_webos_tv.monitor.read_json", side_effect=[
        hardware, network, status, active, last
    ]) as reader:
        result = snapshot()
    assert reader.call_count == 5
    assert result["hardware"]["ambient_c"] == 24.5
    assert result["hardware"]["soc_c"] == 47.5
    assert result["hardware"]["interfaces"]["eth0"]["ipv4"] == ["192.0.2.10"]
    assert result["ocpp"]["connected_count"] == 1
    assert result["ocpp"]["charger_count"] == 2
    assert result["ocpp"]["current"]["id"] == 42
    assert "credential" not in str(result).lower()


def test_monitor_unavailable_is_not_empty():
    with patch("gway_webos_tv.monitor.read_json", return_value=None):
        result = snapshot()
    assert result["hardware"]["available"] is False
    assert result["ocpp"]["available"] is False
    assert result["ocpp"]["active_query_ok"] is False
    assert result["ocpp"]["last_query_ok"] is False
    assert result["ocpp"]["current"] is None


def test_monitor_empty_transactions_are_not_unavailable():
    status = {"schema": "ocpp-csms/status/v1", "data": {"chargers": []}}
    empty = {"schema": "ocpp-csms/transactions/v1", "data": {"transactions": []}}
    with patch("gway_webos_tv.monitor.read_json", side_effect=[
        {}, {"schema": "gway-remote/network/v1", "interfaces": {}}, status, empty, empty
    ]):
        result = snapshot()
    assert result["ocpp"]["available"] is True
    assert result["ocpp"]["active_query_ok"] is True
    assert result["ocpp"]["last_query_ok"] is True
    assert result["ocpp"]["current"] is None
    assert result["ocpp"]["last"] is None


def test_legacy_ip_fallback_when_network_command_unavailable():
    legacy = [{"ifname": "wlan0", "flags": ["UP"], "operstate": "UP",
               "addr_info": [{"family": "inet", "local": "10.42.0.1"}]}]
    with patch("gway_webos_tv.monitor.read_json", side_effect=[
        {"host": {}}, None, legacy, None, None, None
    ]) as reader:
        result = snapshot()
    assert reader.call_count == 6
    assert result["hardware"]["interfaces"]["wlan0"]["ipv4"] == ["10.42.0.1"]
    assert result["hardware"]["interfaces"]["wlan1"]["present"] is False
