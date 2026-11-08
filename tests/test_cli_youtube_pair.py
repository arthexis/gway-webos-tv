"""A4 YouTube aliases and private interactive pairing tests (offline)."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gway_webos_tv import cli
from gway_webos_tv.state import TVError


@pytest.mark.parametrize("words", [
    ["youtube", "search", "openai"],
    ["yt", "s", "openai"],
    ["yts", "openai"],
])
def test_youtube_search_aliases_normalize(words):
    args = cli.parser().parse_args(["--json", *words])
    assert args.command == "youtube"
    assert args.youtube_command == "search"
    assert args.query == ["openai"]
    assert args.wait == 30
    assert args.json is True


@pytest.mark.parametrize("words", [["youtube"], ["yt"]])
def test_youtube_open_aliases(words):
    args = cli.parser().parse_args(words)
    assert args.command == "youtube"
    assert args.youtube_command is None


def test_youtube_search_aliases_share_handler_and_json(tmp_path):
    results = []
    for command in (["youtube", "search", "openai"], ["yt", "s", "openai"], ["yts", "openai"]):
        args = cli.parser().parse_args(["--json", "--state", str(tmp_path / "device.json"), *command])
        tv = MagicMock()
        tv.connect = AsyncMock()
        tv.close = AsyncMock()
        youtube = MagicMock()
        youtube.run = AsyncMock(return_value={"screen": "results", "query": "openai"})
        with patch("gway_webos_tv.youtube.YouTube", return_value=youtube), patch("gway_webos_tv.youtube.validate_query", side_effect=lambda q: q), patch.object(cli, "load_state", return_value=MagicMock()), patch.object(cli, "TV", return_value=tv):
            result = asyncio.run(cli.run(args))
        youtube.run.assert_awaited_once_with("openai")
        tv.close.assert_awaited_once()
        results.append(json.dumps(result, sort_keys=True))
    assert len(set(results)) == 1


@pytest.mark.parametrize("command", [["pair", "--code"], ["pair", "code"]])
def test_pair_code_rejects_json_without_opening_window(command):
    args = cli.parser().parse_args(["--json", *command])
    assert args.code is True
    with patch("gway_webos_tv.event_bridge.open_local_pairing_window") as window, patch.object(cli.sys.stdout, "isatty", return_value=True):
        with pytest.raises(TVError, match="private interactive terminal"):
            asyncio.run(cli.run(args))
        window.assert_not_called()


@pytest.mark.parametrize("command", [["pair", "--code"], ["pair", "code"]])
def test_pair_code_rejects_noninteractive_terminal(command):
    args = cli.parser().parse_args(command)
    with patch("gway_webos_tv.event_bridge.open_local_pairing_window") as window, patch.object(cli.sys.stdout, "isatty", return_value=False):
        with pytest.raises(TVError, match="private interactive terminal"):
            asyncio.run(cli.run(args))
        window.assert_not_called()


@pytest.mark.parametrize("command", [["pair", "--code"], ["pair", "code"]])
def test_pair_code_interactive_local_only(command, capsys):
    args = cli.parser().parse_args(command)
    with patch("gway_webos_tv.event_bridge.open_local_pairing_window", return_value="123456") as window, patch.object(cli.sys.stdout, "isatty", return_value=True), patch.object(cli, "TV") as tv:
        result = asyncio.run(cli.run(args))
    assert result is None
    window.assert_called_once_with()
    tv.assert_not_called()
    assert "123456" in capsys.readouterr().out


def test_pair_plain_still_not_code():
    args = cli.parser().parse_args(["pair"])
    assert args.code is False
