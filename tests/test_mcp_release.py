"""Offline transaction tests; never execute pip, Ansible, MCP or a TV."""
from pathlib import Path

import pytest

from gway_webos_tv.mcp_release import stage


def fixture(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "pyproject.toml").write_text("[build-system]\n")
    root = tmp_path / "root"
    (root / "releases").mkdir(parents=True)
    wheelhouse = tmp_path / "wheels"
    wheelhouse.mkdir()
    lock = tmp_path / "requirements.lock"
    lock.write_text("--require-hashes\ngway-webos-tv==0.2.0 --hash=sha256:" + "a" * 64 + "\n")
    return source, root, "a" * 40, lock, wheelhouse


def fake_runner(calls, fail_at=None):
    def run(argv):
        calls.append(argv)
        if len(calls) == 1:
            (Path(argv[-1]) / "bin").mkdir(parents=True)
        if fail_at == len(calls):
            raise RuntimeError("injected install failure")
    return run


def test_failed_install_leaves_no_final_release(tmp_path):
    args = fixture(tmp_path)
    calls = []
    with pytest.raises(RuntimeError, match="injected"):
        stage(*args, runner=fake_runner(calls, fail_at=2))
    assert list((args[1] / "releases").iterdir()) == []


def test_atomic_promotion_and_second_convergence(tmp_path):
    args = fixture(tmp_path)
    calls = []
    assert stage(*args, runner=fake_runner(calls)) is True
    launcher = args[1] / "releases" / args[2] / "bin/webos-mcp"
    assert launcher.is_file() and launcher.stat().st_mode & 0o111
    assert stage(*args, runner=fake_runner(calls, fail_at=1)) is False
    assert len(calls) == 4


def test_rejects_unlocked_dependencies_and_symlinked_release(tmp_path):
    source, root, sha, lock, wheels = fixture(tmp_path)
    lock.write_text("example>=1\n")
    with pytest.raises(ValueError, match="hash-locked"):
        stage(source, root, sha, lock, wheels, runner=fake_runner([]))
    lock.write_text("--require-hashes\ngway-webos-tv==0.2.0 --hash=sha256:" + "a" * 64)
    (root / "releases" / sha).symlink_to(wheels, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinked"):
        stage(source, root, sha, lock, wheels, runner=fake_runner([]))


def test_rejects_lock_without_application_wheel(tmp_path):
    source, root, sha, lock, wheels = fixture(tmp_path)
    lock.write_text("--require-hashes\\nother==1.0 --hash=sha256:" + "a" * 64)
    with pytest.raises(ValueError, match="application wheel"):
        stage(source, root, sha, lock, wheels, runner=fake_runner([]))


def test_rejects_remote_dependency_directive(tmp_path):
    source, root, sha, lock, wheels = fixture(tmp_path)
    lock.write_text("--require-hashes\\ngway-webos-tv==0.2.0 --hash=sha256:" + "a" * 64 + "\\nhttps://evil.invalid/pkg==1 --hash=sha256:" + "b" * 64)
    with pytest.raises(ValueError, match="unpinned or remote"):
        stage(source, root, sha, lock, wheels, runner=fake_runner([]))
