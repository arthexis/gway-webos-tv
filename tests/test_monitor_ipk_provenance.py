"""Verify that an IPK sidecar binds exact bytes and source revision."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tv_app_provenance", ROOT / "scripts/tv-app.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_ipk_sidecar_verifies_bytes_and_rejects_tampering(tmp_path):
    package = tmp_path / "com.arthexis.gway.monitor_0.1.0_all.ipk"
    package.write_bytes(b"test-ipk-content")
    sha = "a" * 40
    record = {
        "schema": 1, "app_id": "com.arthexis.gway.monitor", "version": "0.1.0",
        "git_sha": sha, "build_id": sha[:16],
        "ipk_sha256": hashlib.sha256(package.read_bytes()).hexdigest()
    }
    sidecar = tmp_path / "build.sha256.json"
    sidecar.write_text(json.dumps(record))
    assert module.verify_package_sidecar(package, sidecar)["git_sha"] == sha
    package.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="verification failed"):
        module.verify_package_sidecar(package, sidecar)
    package.write_bytes(b"test-ipk-content")
    record["build_id"] = "wrong"
    sidecar.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="verification failed"):
        module.verify_package_sidecar(package, sidecar)
