"""Isolated DOM diagnostic checks; never derive the badge from the collector."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js unavailable")
def test_dom_diagnostic_reads_rendered_badge_and_rejects_stale_nonce():
    script = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const badge = {getAttribute: () => 'Installed', querySelector: () => ({textContent:'Installed'})};
const card = {querySelector: selector => selector === 'h2' ?
  {textContent:'arthexis/gway-agent-ops'} : badge};
const root = {hidden:false, querySelectorAll: () => [card]};
const document = {getElementById: () => root};
const ctx = {window:{}, document, Date, Number};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
const d = ctx.window.GwayMonitorDiagnostic;
const request = {type:'monitor.diagnostic.request', nonce:'a'.repeat(32),
  expires_at:Date.now()+1000, repository:'arthexis/gway-agent-ops'};
const identity = {build_id:'abcd',git_sha:'a'.repeat(40)};
assert.equal(d.evidence(request,identity,Date.now()).card.badge,'Installed');
assert.equal(d.evidence(request,identity,Date.now()).card.aria_label,'Installed');
assert.equal(d.evidence({...request,expires_at:Date.now()-1},identity,Date.now()),null);
assert.equal(d.evidence({...request,nonce:'invalid'},identity,Date.now()),null);
assert.equal(d.evidence({...request,repository:'another/repo'},identity,Date.now()),null);
root.hidden = true;
assert.equal(d.evidence(request,identity,Date.now()).card,null);
"""
    result = subprocess.run(
        ["node", "-e", script, str(ROOT / "apps/gway-monitor/diagnostic.js")],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr
