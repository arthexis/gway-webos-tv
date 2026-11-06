from gway_webos_tv.cli import main, parser


def test_pair_defaults_to_tv():
    assert parser().parse_args(['pair']).code is False


def test_pair_bridge_is_separate():
    args = parser().parse_args(['pair', '--code'])
    assert args.command == 'pair'
    assert args.code is True


def test_pair_bridge_refuses_non_tty(capsys):
    assert main(['pair', '--code']) == 1
    assert 'private interactive terminal' in capsys.readouterr().err
