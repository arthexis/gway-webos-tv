"""A5 canonical dispatcher and security tests: no physical TV."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from gway_webos_tv.cli import normalize, parser
from gway_webos_tv.dispatcher import Operation, dispatch
from gway_webos_tv.state import TVError


@pytest.mark.parametrize(("aliases", "expected"), [
    (["inputs"], "inputs.list"), (["inputs", "list"], "inputs.list"),
    (["hdmi", "2"], "inputs.select"), (["inputs", "select", "2"], "inputs.select"),
    (["apps"], "apps.list"), (["apps", "list"], "apps.list"),
    (["launch", "browser"], "apps.launch"), (["apps", "launch", "browser"], "apps.launch"),
    (["screenshot"], "screen.capture"), (["sc"], "screen.capture"),
    (["screen", "capture"], "screen.capture"),
    (["youtube"], "youtube.open"), (["yt"], "youtube.open"),
    (["youtube", "search", "openai"], "youtube.search"),
    (["yt", "s", "openai"], "youtube.search"), (["yts", "openai"], "youtube.search"),
    (["pair"], "pair"), (["pair", "--code"], "pair.code"), (["pair", "code"], "pair.code"),
    (["status"], "status"),
])
def test_normalize_aliases(aliases, expected):
    assert normalize(parser().parse_args(aliases)).name == expected


def test_pairing_cannot_be_dispatched():
    for name in ("pair", "pair.code"):
        with pytest.raises(TVError, match="local interactive"):
            asyncio.run(dispatch(MagicMock(), Operation(name)))


def test_unknown_operation_rejected():
    with pytest.raises(TVError, match="Unsupported"):
        Operation("shell.execute", {"command": "id"})


def test_capture_requires_explicit_local_saver():
    with pytest.raises(TVError, match="explicit local save"):
        asyncio.run(dispatch(MagicMock(), Operation("screen.capture")))


@pytest.mark.parametrize(("old", "new", "method", "result"), [
    (["inputs"], ["inputs", "list"], "inputs", [{"id": "hdmi_1"}]),
    (["hdmi", "2"], ["inputs", "select", "2"], "hdmi", {"verified": True}),
    (["apps"], ["apps", "list"], "apps", [{"id": "browser"}]),
    (["launch", "browser"], ["apps", "launch", "browser"], "launch", {"verified": True}),
])
def test_dispatch_alias_parity(old, new, method, result):
    outputs = []
    for words in (old, new):
        op = normalize(parser().parse_args(words))
        tv = MagicMock()
        setattr(tv, method, AsyncMock(return_value=result))
        outputs.append(asyncio.run(dispatch(tv, op)))
        getattr(tv, method).assert_awaited_once()
    assert outputs[0] == outputs[1]


def test_capture_json_shape():
    tv = MagicMock()
    tv.capture = AsyncMock(return_value=(b"abc", ".jpg"))
    result = asyncio.run(dispatch(tv, Operation("screen.capture", {"output": Path("image.jpg")}), save_capture=lambda *_: Path("image.jpg")))
    assert result == {"path": "image.jpg", "bytes": 3, "source": "tv", "format": "jpg"}
