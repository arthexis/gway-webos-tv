"""TV readability/status and distinct launcher icon regressions."""
import importlib.util
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/gway-monitor"


def test_launcher_icons_distinct_and_valid_png(tmp_path):
    spec = importlib.util.spec_from_file_location("launcher_icons", ROOT / "scripts/launcher_icons.py")
    icons = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(icons)
    images = []
    for name in ("gway-monitor", "remote-test"):
        output = tmp_path / (name + ".png")
        assert icons.generate_icon(name, output)
        data = output.read_bytes()
        assert data[:8] == bytes.fromhex("89504e470d0a1a0a")
        assert struct.unpack(">II", data[16:24]) == (160, 160)
        images.append(data)
    assert images[0] != images[1]


def test_monitor_readability_and_script_order():
    css = (APP / "style.css").read_text()
    assert "padding:3vh 2vw" in css
    assert ".status-symbol" in css and "78px" in css
    html = (APP / "index.html").read_text()
    assert html.index('src="core/status.js"') < html.index('src="channels/github.js"')


@pytest.mark.skipif(shutil.which("node") is None, reason="Node unavailable")
def test_status_priority_and_rendered_badges():
    script = r"""
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const doc={createElement(tag){return {tag,className:'',textContent:'',attrs:{},children:[],
  setAttribute(k,v){this.attrs[k]=v},appendChild(c){this.children.push(c)}}}};
const context={window:{},document:doc};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
const s=context.window.GwayMonitorStatus;
assert.equal(s.github({ci:'failed',merge:'CLEAN'}).level,'failed');
assert.equal(s.github({ci:'passed',merge:'DIRTY'}).level,'failed');
assert.equal(s.github({ci:'passed',merge:'CLEAN'}).level,'passed');
assert.equal(s.github({ci:'passed',merge:'BEHIND'}).level,'unknown');
assert.equal(s.github({ci:'pending'}).level,'pending');
assert.equal(s.github({draft:true,ci:'unknown'}).level,'draft');
assert.equal(s.github({ci:'unknown'}).level,'unknown');
assert.equal(s.deployment({installation:'installed',health:'healthy'}).level,'passed');
assert.equal(s.deployment({installation:'installed',health:'healthy',outdated:true}).level,'outdated');
assert.equal(s.deployment({installation:'installed',health:'failed',outdated:true}).level,'failed');
assert.equal(s.deployment({installation:'deploying',health:'unknown'}).level,'pending');
assert.equal(s.deployment({installation:'installed',health:'degraded'}).level,'degraded');
assert.equal(s.deployment({installation:'unknown',health:'unknown'}).level,'unknown');
assert.equal(s.deployment({installation:'installed',health:'healthy',target_revision:'abc',revision:'def'}).level,'outdated');
const badge=s.badge(s.github({ci:'passed',merge:'CLEAN'}));
assert.equal(badge.attrs['aria-label'],'Ready');
assert.equal(badge.children.length,2);
"""
    result = subprocess.run(["node", "-e", script, str(APP / "core/status.js")],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
