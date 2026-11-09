import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js unavailable")
def test_staged_bastion_badge():
    status = Path(__file__).resolve().parents[1] / "apps/gway-monitor/core/status.js"
    script = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const ctx = {window: {}};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const deployment = ctx.window.GwayMonitorStatus.deployment;
const staged = {name:'gway-bastion', installation:'staged', health:'not_applicable',
  staged_revision:'a'.repeat(40), revision:null, verified_release:false};
assert.equal(deployment(staged).label, 'Staged');
assert.notEqual(deployment(staged).level, 'passed');
assert.equal(deployment({...staged, staged_revision:null}).label, 'Unknown');
assert.equal(deployment({...staged, name:'ocpp-csms'}).label, 'Unknown');
"""
    result = subprocess.run(
        ["node", "-e", script, str(status)],
        capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
