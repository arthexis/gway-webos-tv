"""Fast node-only contract tests for visible status semantics and no unsafe HTML."""
import shutil
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/gway-monitor"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node unavailable")
def test_distinct_tv_status_chips_and_unknown_state_are_safe():
    code = r"""
const assert=require('assert'),fs=require('fs'),vm=require('vm');
function element() {return {className:'',textContent:'',children:[],attrs:{},
  appendChild(x){this.children.push(x)},setAttribute(k,v){this.attrs[k]=v}};}
const context={window:{},document:{createElement:element}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
const s=context.window.GwayMonitorStatus;
assert.equal(s.signal('ci','failed'),'failed');
assert.equal(s.signal('ci','pending'),'pending');
assert.equal(s.signal('ci','not_applicable'),'unknown');
assert.equal(s.signal('merge','CLEAN'),'passed');
assert.equal(s.signal('merge','BLOCKED'),'failed');
assert.equal(s.signal('merge','BEHIND'),'pending');
assert.equal(s.signal('installation','staged'),'degraded');
assert.equal(s.signal('health','not_applicable'),'unknown');
const malicious='<img src=x onerror=alert(1)>';
const chip=s.chip('Health',malicious,'unknown');
assert.equal(chip.attrs['aria-label'],'Health: '+malicious);
assert.equal(chip.children.length,2);
assert.equal(chip.children[1].textContent,'Health: '+malicious);
assert.equal(chip.className,'tv-chip status-unknown');
assert.equal(s.chip('CI','passed','attacker-css').className,'tv-chip status-unknown');
"""
    run = subprocess.run(["node", "-e", code, str(APP / "core/status.js")],
                         capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr


def test_tv_layout_breakpoint_and_full_sha_auditable():
    css = (APP / "style.css").read_text()
    assert "@media (min-width:1200px)" in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert "#github .github-title" in css and "font-size:32px" in css
    assert "#deployments .deployment-name" in css and "font-size:30px" in css
    deployment = (APP / "channels/deployments.js").read_text()
    assert "data-full-revision" in deployment
    assert "selected-card" in deployment
    assert "status.deployment(item).level === 'failed'" in deployment
