"""Provider manifest validation; no TV access."""

import pytest

from gway_webos_tv.mcp_manifest import manifest

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
