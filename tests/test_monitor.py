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
    interfaces = [
        {"ifname": "eth0", "addr_info": [{"family": "inet", "local": "192.0.2.10"}]},
        {"ifname": "wlan0", "addr_info": [{"family": "inet", "local": "192.0.2.11"}]},
    ]
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
        hardware, interfaces, status, active, last
    ]) as reader:
        result = snapshot()
    assert reader.call_count == 5
    assert result["hardware"]["ambient_c"] == 24.5
    assert result["hardware"]["soc_c"] == 47.5
    assert result["hardware"]["interfaces"]["eth0"] == ["192.0.2.10"]
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
        {}, [], status, empty, empty
    ]):
        result = snapshot()
    assert result["ocpp"]["available"] is True
    assert result["ocpp"]["active_query_ok"] is True
    assert result["ocpp"]["last_query_ok"] is True
    assert result["ocpp"]["current"] is None
    assert result["ocpp"]["last"] is None
