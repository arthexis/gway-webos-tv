"""CLI application command compatibility tests."""

from gway_webos_tv.cli import parser


def test_apps_list_and_legacy_apps_parse_identically():
    legacy = parser().parse_args(["apps"])
    nested = parser().parse_args(["apps", "list"])
    assert legacy.command == nested.command == "apps"
    assert legacy.apps_command is None
    assert nested.apps_command == "list"


def test_apps_unknown_subcommand_rejected():
    import pytest

    with pytest.raises(SystemExit) as exc:
        parser().parse_args(["apps", "delete"])
    assert exc.value.code == 2


def test_apps_launch_matches_legacy_launch_arguments():
    legacy = parser().parse_args(["launch", "com.webos.app.browser", "--wait", "45"])
    nested = parser().parse_args(["apps", "launch", "com.webos.app.browser", "--wait", "45"])
    assert legacy.command == "launch"
    assert nested.command == "apps"
    assert nested.apps_command == "launch"
    assert legacy.app_id == nested.app_id == "com.webos.app.browser"
    assert legacy.wait == nested.wait == 45


def test_apps_launch_requires_app_id():
    import pytest

    with pytest.raises(SystemExit) as exc:
        parser().parse_args(["apps", "launch"])
    assert exc.value.code == 2
