"""Offline subprocess contract for CI-pinned webOS node activation."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
OTHER = "b" * 40


def fake(path, script):
    path.write_text("#!/bin/sh\nset -eu\n" + script)
    path.chmod(0o755)


def fixture(tmp_path):
    home = tmp_path / "home"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (home / ".config/gway-webos-tv").mkdir(parents=True)
    (home / ".config/gway-webos-tv/deploy.env").write_text("GWAY_WEBOS_BRIDGE_LISTEN=10.90.0.2\n")
    fake(bindir / "id", 'if [ "$1" = "-u" ]; then echo 1000; else echo arthe; fi\n')
    fake(
        bindir / "git",
        """case "$*" in
    *"branch --show-current") echo main;;
    *"status --porcelain") :;;
    *"fetch --quiet origin main") :;;
    *"rev-parse refs/remotes/origin/main") printf '%s\\n' "$MOCK_REMOTE_SHA";;
    *"rev-parse HEAD") printf '%s\\n' "$MOCK_LOCAL_SHA";;
    *) echo "Unexpected git operation: $*" >&2; exit 9;;
esac
""",
    )
    fake(bindir / "ansible-playbook", 'printf "%s\\n" "$@" > "$MOCK_ANSIBLE_ARGS"\n')
    fake(bindir / "systemctl", 'exit 1\n')
    env = dict(os.environ, HOME=str(home), PATH=str(bindir) + os.pathsep + os.environ["PATH"],
               MOCK_LOCAL_SHA=SHA, MOCK_REMOTE_SHA=SHA,
               MOCK_ANSIBLE_ARGS=str(tmp_path / "ansible.args"))
    return home, env


def run(env):
    return subprocess.run(["sh", str(ROOT / "deploy.sh")], env=env, capture_output=True, text=True)


def test_pinned_release_forces_ansible_activation_even_when_git_preupdated(tmp_path):
    home, env = fixture(tmp_path)
    env["GWAY_WEBOS_EXPECTED_SHA"] = SHA
    result = run(env)
    assert result.returncode == 0, result.stderr
    args = (tmp_path / "ansible.args").read_text().splitlines()
    assert "-c" in args and "local" in args
    assert f"gway_webos_expected_sha={SHA}" in args
    assert "gway_webos_activate=true" in args
    assert (home / ".local/state/gway-webos-tv/deployed.sha").read_text().strip() == SHA + " 10.90.0.2"


def test_ci_expected_sha_mismatch_fails_before_ansible(tmp_path):
    home, env = fixture(tmp_path)
    env["GWAY_WEBOS_EXPECTED_SHA"] = OTHER
    result = run(env)
    assert result.returncode == 2
    assert "CI-gated SHA differs" in result.stderr
    assert not (tmp_path / "ansible.args").exists()
    assert not (home / ".local/state/gway-webos-tv/deployed.sha").exists()


def test_moving_origin_fails_closed(tmp_path):
    home, env = fixture(tmp_path)
    env["MOCK_REMOTE_SHA"] = OTHER
    env["GWAY_WEBOS_EXPECTED_SHA"] = SHA
    result = run(env)
    assert result.returncode == 2
    assert not (tmp_path / "ansible.args").exists()
    assert not (home / ".local/state/gway-webos-tv/deployed.sha").exists()


def test_non_hex_expected_sha_rejected(tmp_path):
    _, env = fixture(tmp_path)
    env["GWAY_WEBOS_EXPECTED_SHA"] = "x" * 40
    result = run(env)
    assert result.returncode == 2
    assert not (tmp_path / "ansible.args").exists()
