"""Offline A7 contract tests. Never invoke Ansible or access a TV."""

from pathlib import Path

import pytest

from gway_webos_tv.mcp_manifest import manifest

ROOT = Path(__file__).resolve().parents[1]


def test_provider_is_part_of_normal_installation():
    playbook = (ROOT / "ansible/deploy.yml").read_text()
    assert "gway_webos_mcp_enable" not in playbook
    assert "include_tasks: tasks/webos-mcp.yml" in playbook
    assert "when: gway_webos_mcp_enable | bool" not in playbook


def test_normal_install_manifest_without_wheelhouse_or_rollback():
    tasks = (ROOT / "ansible/tasks/webos-mcp.yml").read_text()
    assert "mcp-requirements.lock" not in tasks
    assert "wheelhouse" not in tasks
    assert "rescue:" not in tasks
    assert "gway_webos_tv.mcp_manifest" in tasks
    assert "gway_webos_tv.mcp_stdio" in tasks
    assert "ansible.builtin.copy:" in tasks
    assert "mode: '0644'" in tasks
    assert "/etc/gway-mcp-providers/webos.json" in tasks


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


def test_manifest_rejects_symlinked_provider(tmp_path):
    release = tmp_path / ("c" * 40)
    executable = release / "bin/webos-mcp"
    executable.parent.mkdir(parents=True)
    target = tmp_path / "other"
    target.write_text("#!/bin/sh\\n")
    target.chmod(0o755)
    executable.symlink_to(target)
    with pytest.raises(ValueError, match="executable missing"):
        manifest(release)
