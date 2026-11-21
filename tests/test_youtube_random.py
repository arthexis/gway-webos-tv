"""Offline randomizer provider, CLI/MCP routing, and browser handoff tests."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from gway_webos_tv.cli import normalize, parser
from gway_webos_tv.client import TV
from gway_webos_tv.dispatcher import Operation, dispatch
from gway_webos_tv.mcp_stdio import EXECUTE, READ, validate
from gway_webos_tv.randomizers import randomizer_url
from gway_webos_tv.state import Device, TVError


@pytest.mark.parametrize(
    "service,category,url",
    [
        ("random-video", None, "https://random-video.com/"),
        ("ytroulette", None, "https://ytroulette.com/en/"),
        ("ytroulette", "music", "https://ytroulette.com/en/music"),
        ("ytroulette", "sports", "https://ytroulette.com/en/sports"),
        ("ytroulette", "gaming", "https://ytroulette.com/en/gaming"),
        ("ytroulette", "zero", "https://ytroulette.com/en/zero"),
        ("obscuretube", None, "https://obscuretube.com/"),
    ],
)
def test_only_predefined_randomizer_destinations(service, category, url):
    assert randomizer_url(service, category) == url


@pytest.mark.parametrize(
    "service,category",
    [
        ("invalid", None), ("https://example.test", None), ("random-video", "music"),
        ("obscuretube", "zero"), ("ytroulette", "anything"),
    ],
)
def test_invalid_or_incompatible_randomizer_options_fail_closed(service, category):
    with pytest.raises(TVError):
        randomizer_url(service, category)


@pytest.mark.parametrize("alias", ["random", "r"])
def test_cli_random_alias_and_options(alias):
    args = parser().parse_args(
        ["--json", "youtube", alias, "--service", "ytroulette", "--category", "music"]
    )
    op = normalize(args)
    assert op == Operation("youtube.random", {"service": "ytroulette", "category": "music", "wait": 30})


def test_yt_short_alias_and_wait_override():
    args = parser().parse_args(["yt", "random", "--wait", "40"])
    assert normalize(args) == Operation(
        "youtube.random", {"service": "random-video", "category": None, "wait": 40}
    )


def test_random_is_execute_only_and_rejects_arbitrary_destinations():
    assert "youtube.random" in EXECUTE
    assert "youtube.random" not in READ
    assert validate("execute", {"operation": "youtube.random"}).name == "youtube.random"
    assert validate("execute", {"operation": "youtube.random", "service": "ytroulette", "category": "zero"}).params["category"] == "zero"
    for args in [
        {"operation": "youtube.random", "service": "https://example.test"},
        {"operation": "youtube.random", "service": "random-video", "category": "music"},
        {"operation": "youtube.random", "url": "https://example.test"},
    ]:
        with pytest.raises((ValueError, TVError)):
            validate("execute", args)
    with pytest.raises(ValueError, match="operation_not_allowed"):
        validate("read", {"operation": "youtube.random"})


def test_dispatch_opens_service_without_youtube_ocr_or_fake_playback():
    class FakeTV:
        open_browser = AsyncMock(
            return_value={
                "foreground_app": "com.webos.app.browser",
                "browser_verified": True,
                "video_verified": False,
            }
        )

    tv = FakeTV()
    result = asyncio.run(
        dispatch(
            tv,
            Operation("youtube.random", {"service": "ytroulette", "category": "music", "wait": 20}),
        )
    )
    tv.open_browser.assert_awaited_once_with("https://ytroulette.com/en/music", 20)
    assert result["service"] == "ytroulette"
    assert result["browser_verified"] is True
    assert result["video_verified"] is False


def test_browser_launch_requires_foreground_confirmation():
    tv = TV(Device("192.0.2.50"))
    calls = []

    class FakeClient:
        async def request(self, uri, body):
            calls.append((uri, body))
            return {"returnValue": True}

    tv.client = FakeClient()
    tv.wait_foreground = AsyncMock(return_value="com.webos.app.browser")
    result = asyncio.run(tv.open_browser("https://random-video.com/", 30))
    assert calls == [
        ("ssap://system.launcher/open", {"target": "https://random-video.com/"})
    ]
    tv.wait_foreground.assert_awaited_once_with("com.webos.app.browser", 30)
    assert result["video_verified"] is False
