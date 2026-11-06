from unittest.mock import AsyncMock

import pytest

from gway_webos_tv.cli import render
from gway_webos_tv.client import TV
from gway_webos_tv.state import Device


@pytest.mark.asyncio
async def test_apps_include_versions_and_missing_version():
    tv = TV(Device("192.0.2.1"))
    tv.client = type("Client", (), {})()
    tv.client.get_apps_all = AsyncMock(return_value=[
        {"id": "com.arthexis.gway.monitor", "title": "GWAY Monitor", "version": "0.1.0"},
        {"id": "com.example.unknown", "title": "Unknown"},
    ])
    assert await tv.apps() == [
        {"id": "com.arthexis.gway.monitor", "title": "GWAY Monitor", "version": "0.1.0"},
        {"id": "com.example.unknown", "title": "Unknown", "version": None},
    ]


def test_apps_text_output(capsys):
    render({"apps": [{"id": "a", "title": "App", "version": "1.2.3"},
                     {"id": "b", "title": "Other", "version": None}]})
    assert capsys.readouterr().out == (
        "a\tApp\tversion=1.2.3\n"
        "b\tOther\tversion=unknown\n"
    )
