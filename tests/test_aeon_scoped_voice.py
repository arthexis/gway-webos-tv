import asyncio
from pathlib import Path

import pytest

from gway_webos_tv.aeon_scoped_voice import (
    APP, SOURCE, capture_context, config_text, sandbox_command, sha, stage_sources,
)
from gway_webos_tv.aeon_voice import VoiceDenied


class FakeTV:
    def __init__(self, apps):
        self.apps = iter(apps)
        self.client = self
        self.captures = 0

    async def get_current_app(self):
        return next(self.apps)

    async def call(self, action):
        return await action

    async def capture(self):
        self.captures += 1
        return b"test screenshot", ".jpg"


def test_capture_rejects_other_app(tmp_path):
    async def check():
        tv = FakeTV(["youtube.leanback.v4"])
        with pytest.raises(VoiceDenied):
            await capture_context(tv, tmp_path)
        assert tv.captures == 0
        tv = FakeTV([APP, "com.webos.app.home"])
        with pytest.raises(VoiceDenied):
            await capture_context(tv, tmp_path)
        assert not list(tmp_path.iterdir())
        tv = FakeTV([APP, APP])
        r = await capture_context(tv, tmp_path)
        assert r["sha256"] == sha(tmp_path / r["file"])
    asyncio.run(check())


def test_source_stage_and_profile(tmp_path):
    source = Path(__file__).resolve().parents[1] / "experiments/aeon-rpg-player/demo"
    game = tmp_path / "game"
    game.mkdir()
    stage_sources(source, game)
    assert {p.name: sha(p) for p in game.iterdir()} == SOURCE
    with pytest.raises(VoiceDenied):
        stage_sources(tmp_path, game)
    cfg = config_text(game, tmp_path / "runtime", tmp_path / "context")
    assert 'default_permissions = "aeon"' in cfg
    assert 'enabled = false' in cfg
    assert f'"{game}" = "write"' in cfg
    cmd = sandbox_command(tmp_path / "runtime", game, tmp_path / "config",
                          tmp_path / "context", tmp_path / "auth", tmp_path / "pulse")
    assert "--clearenv" in cmd and "--die-with-parent" in cmd
    assert cmd[cmd.index(str(tmp_path / "auth")) - 1] == "--ro-bind"
