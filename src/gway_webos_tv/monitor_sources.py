"""Hardware and OCPP read-only monitor providers. Preserve legacy payload shape."""


def hardware_snapshot(read_json):
    hardware = read_json(["/usr/local/bin/gway-remote", "hardware", "--json"])
    network = read_json(["/usr/local/bin/gway-remote", "network", "--json"])
    interfaces = None
    if not (
        isinstance(network, dict)
        and network.get("schema") == "gway-remote/network/v1"
        and isinstance(network.get("interfaces"), dict)
    ):
        # Transitional fallback while gway-remote/network/v1 rolls out to nodes.
        interfaces = read_json(["/usr/sbin/ip", "-4", "-j", "address", "show"])
    host = hardware.get("host", {}) if isinstance(hardware, dict) else {}
    ambient = hardware.get("ambient_temperature", {}) if isinstance(hardware, dict) else {}
    ips = {}
    if (
        isinstance(network, dict)
        and network.get("schema") == "gway-remote/network/v1"
        and isinstance(network.get("interfaces"), dict)
    ):
        for name in ("eth0", "wlan0", "wlan1"):
            item = network.get("interfaces", {}).get(name)
            if isinstance(item, dict):
                ips[name] = {
                    "present": item.get("present") is True,
                    "up": item.get("up") is True,
                    "operstate": item.get("operstate"),
                    "ipv4": item.get("ipv4") if isinstance(item.get("ipv4"), list) else [],
                }
    if isinstance(interfaces, list):
        for item in interfaces:
            if isinstance(item, dict) and item.get("ifname") in ("wlan0", "wlan1", "eth0"):
                ips[item["ifname"]] = {
                    "present": True,
                    "up": "UP" in item.get("flags", []),
                    "operstate": item.get("operstate"),
                    "ipv4": [
                        x.get("local")
                        for x in item.get("addr_info", [])
                        if isinstance(x, dict)
                        and x.get("family") == "inet"
                        and isinstance(x.get("local"), str)
                    ],
                }

    for name in ("eth0", "wlan0", "wlan1"):
        ips.setdefault(name, {"present": False, "up": False, "operstate": None, "ipv4": []})

    return {
        "available": bool(hardware),
        "ambient_c": ambient.get("celsius"),
        "soc_c": host.get("cpu_temperature_c"),
        "model": host.get("model"),
        "uptime_seconds": host.get("uptime_seconds"),
        "cpu_frequency_mhz": host.get("cpu_frequency_mhz"),
        "memory": host.get("memory"),
        "disk": host.get("root_filesystem"),
        "interfaces": ips,
    }


def ocpp_snapshot(read_json):
    status = read_json(["/usr/local/bin/ocpp-csms", "status", "--json"])
    active = read_json(["/usr/local/bin/ocpp-csms", "txn", "--active", "--json"])
    last = read_json(["/usr/local/bin/ocpp-csms", "txn", "--last", "--json"])

    def data(doc, schema):
        return (
            doc.get("data", {})
            if isinstance(doc, dict)
            and doc.get("schema") == schema
            and isinstance(doc.get("data"), dict)
            else None
        )

    csms = data(status, "ocpp-csms/status/v1")
    current = data(active, "ocpp-csms/transactions/v1")
    recent = data(last, "ocpp-csms/transactions/v1")

    def tx(doc):
        items = doc.get("transactions", []) if isinstance(doc, dict) else []
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            return None
        row = items[0]
        return {
            key: row.get(key)
            for key in (
                "id",
                "charger_id",
                "connector_id",
                "state",
                "active",
                "started_at",
                "stopped_at",
                "energy_wh",
            )
        }

    chargers = csms.get("chargers", []) if csms else []
    if not isinstance(chargers, list):
        chargers = []
    return {
        "available": csms is not None,
        "server": csms.get("server") if csms else None,
        "storage": csms.get("storage") if csms else None,
        "charger_count": len(chargers),
        "connected_count": sum(
            1 for c in chargers if isinstance(c, dict) and c.get("connected") is True
        ),
        "active_query_ok": current is not None,
        "last_query_ok": recent is not None,
        "current": tx(current),
        "last": tx(recent),
    }