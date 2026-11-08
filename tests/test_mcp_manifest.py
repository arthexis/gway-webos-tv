"""Node-owned provider manifest validation."""

import json

import pytest

from gway_webos_tv.mcp_manifest import manifest


def test_manifest_pinned_executable(tmp_path):
    release = tmp_path / ("a" * 40)
    executable = release / "bin" / "webos-mcp"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o700)
    result = manifest("a" * 40, executable)
    assert result == {"source_id": "webos", "revision": "a" * 40,
                      "executable": str(executable), "argv": [str(executable)]}
    assert json.loads(json.dumps(result)) == result


def test_manifest_rejects_unpinned_and_nonexecutable(tmp_path):
    release = tmp_path / "unversioned"
    executable = release / "bin" / "webos-mcp"
    executable.parent.mkdir(parents=True)
    executable.write_text("not executable")
    with pytest.raises(ValueError):
        manifest('invalid', executable)
    pinned = tmp_path / ("b" * 40)
    target = pinned / "bin" / "webos-mcp"
    target.parent.mkdir(parents=True)
    target.write_text("not executable")
    with pytest.raises(ValueError, match="executable missing"):
        manifest("b" * 40, target)
