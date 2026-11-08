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


def test_generator_checks_transitive_closure_and_real_hash(tmp_path):
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / "scripts/build_mcp_lock.py"
    spec = spec_from_file_location("build_mcp_lock", script)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    wheel = tmp_path / "gway_webos_tv-0.2.0-py3-none-any.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr("gway_webos_tv-0.2.0.dist-info/METADATA",
                         "Metadata-Version: 2.1\\nName: gway-webos-tv\\nVersion: 0.2.0\\nRequires-Dist: example>=1\\n")
    with pytest.raises(ValueError, match="missing transitive"):
        module.build_lock(tmp_path)
    dependency = tmp_path / "example-1.2-py3-none-any.whl"
    with ZipFile(dependency, "w") as archive:
        archive.writestr("example-1.2.dist-info/METADATA",
                         "Metadata-Version: 2.1\\nName: example\\nVersion: 1.2\\n")
    lock = module.build_lock(tmp_path)
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() in lock
    assert hashlib.sha256(dependency.read_bytes()).hexdigest() in lock
