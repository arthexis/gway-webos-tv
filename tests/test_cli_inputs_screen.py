"""A3 command aliases and machine-readable result compatibility (no real TV)."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gway_webos_tv import cli


@pytest.mark.parametrize(
    ("legacy", "nested", "operation"),
    [
        (["inputs"], ["inputs", "list"], "inputs"),
        (["hdmi", "2", "--wait", "45"], ["inputs", "select", "2", "--wait", "45"], "hdmi"),
        (["screenshot", "capture.jpg"], ["screen", "capture", "capture.jpg"], "capture"),
        (["sc"], ["screen", "capture"], "capture"),
    ],
)
def test_command_aliases_use_same_handler_and_json(legacy, nested, operation, tmp_path):
    outputs = []
    for command in (legacy, nested):
        args = cli.parser().parse_args(["--json", "--state", str(tmp_path / "pair.json"), *command])
        tv = MagicMock()
        tv.connect = AsyncMock()
        tv.close = AsyncMock()
        tv.inputs = AsyncMock(return_value=[{"id": "hdmi_1", "label": "HDMI 1", "connected": True}])
        tv.hdmi = AsyncMock(return_value={"verified": True, "foreground_app": "com.webos.app.hdmi2"})
        tv.capture = AsyncMock(return_value=(b"image", ".jpg"))
        with patch.object(cli, "load_state", return_value=MagicMock()), patch.object(cli, "TV", return_value=tv), patch.object(cli, "save_image", return_value=Path("capture.jpg")):
            result = asyncio.run(cli.run(args))
        getattr(tv, operation).assert_awaited_once()
        tv.close.assert_awaited_once()
        outputs.append(json.dumps(result, sort_keys=True))
    assert outputs[0] == outputs[1]


def test_select_aliases_preserve_wait_and_hdmi_number():
    legacy = cli.parser().parse_args(["hdmi", "2", "--wait", "45"])
    nested = cli.parser().parse_args(["inputs", "select", "2", "--wait", "45"])
    assert (legacy.number, legacy.wait) == (nested.number, nested.wait) == (2, 45)


@pytest.mark.parametrize("command", [["inputs", "select", "9"], ["screen"], ["inputs", "delete"]])
def test_invalid_subcommands_fail_without_connecting(command):
    with pytest.raises(SystemExit) as error:
        cli.parser().parse_args(command)
    assert error.value.code == 2
