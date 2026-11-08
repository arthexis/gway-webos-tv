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
