"""Offline A7 contract tests. Never invoke Ansible or access a TV."""

from pathlib import Path

import pytest

from gway_webos_tv.mcp_manifest import manifest

ROOT = Path(__file__).resolve().parents[1]


def test_opt_in_in_existing_playbook():
    playbook = (ROOT / "ansible/deploy.yml").read_text()
    assert "gway_webos_mcp_enable: false" in playbook
    assert "include_tasks: tasks/webos-mcp.yml" in playbook
    assert "when: gway_webos_mcp_enable | bool" in playbook


def test_pinned_release_atomic_manifest_and_rollback_contract():
    tasks = (ROOT / "ansible/tasks/webos-mcp.yml").read_text()
    for contract in (
        "gway_webos_checkout.after == gway_webos_mcp_revision",
        "^[0-9a-f]{40}$", "/opt/gway-webos-tv/releases/",
        "gway_webos_tv.mcp_manifest", "/etc/gway-mcp-providers/webos.json",
        "owner: root", "group: root", "mode: '0644'", "ansible.builtin.copy:",
        "rescue:", "webos_mcp_previous.content | b64decode",
        "webos_mcp_old_stat.stat.exists", "changed_when: false",
    ):
        assert contract in tasks
    assert "shell:" not in tasks
    assert "state: restarted" not in tasks


def test_manifest_requires_pinned_installed_executable(tmp_path):
    release = tmp_path / ("a" * 40)
    executable = release / "bin/webos-mcp"
    executable.parent.mkdir(parents=True)
    with pytest.raises(ValueError):
        manifest(release)
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o755)
    result = manifest(release)
    assert result["source_id"] == "webos"
    assert result["revision"] == "a" * 40
    assert result["argv"] == [str(executable)]
