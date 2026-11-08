"""Verify real digest generation and transitive dependency closure offline."""
import hashlib
from zipfile import ZipFile

import pytest

from gway_webos_tv.mcp_wheelhouse import verify


def test_wheel_hash_integrity_and_tamper(tmp_path):
    wheel = tmp_path / "gway_webos_tv-0.2.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel bytes")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    lock = tmp_path / "mcp.lock"
    lock.write_text("--require-hashes\ngway-webos-tv==0.2.0 --hash=sha256:" + digest + "\n")
    assert verify(lock, tmp_path) == 1
    wheel.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="mismatched"):
        verify(lock, tmp_path)
