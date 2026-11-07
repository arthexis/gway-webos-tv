"""Increment C: independent frontend modules and packaging compatibility."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps" / "gway-monitor"
NAMES = ("hardware", "ocpp", "github", "deployments", "fleet")


def test_all_channel_modules_are_staged_and_ordered():
    html = (APP / "index.html").read_text()
    scripts = ["secret-dialog.js", "core/format.js", "channel-registry.js"]
    scripts += [f"channels/{name}.js" for name in NAMES]
    scripts += ["app.js"]
    offsets = [html.index(f'src="{name}"') for name in scripts]
    assert offsets == sorted(offsets)
    assert all((APP / name).is_file() for name in scripts)
    core = (APP / "app.js").read_text()
    assert "function renderHardware" not in core
    assert "function renderOcpp" not in core
    assert "function renderGithub" not in core
    assert "function renderDeployments" not in core
    assert "function renderFleet" not in core
    assert core.count("var url = localStorage.getItem('gway.bridge.url') || '';") == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="Node unavailable")
def test_all_channel_modules_execute_and_navigate():
    script = r"""
const assert = require('assert'), fs = require('fs'), vm = require('vm'), path = require('path');
const root = process.argv[1];
function element(id) {
  return {
    id, hidden:false, textContent:'', className:'', children:[],
    classList:{toggle:()=>{}},
    appendChild(child){this.children.push(child)},
    setAttribute(){},
    scrollIntoView(){}
  };
}
const elements = {};
const document = {
  getElementById(id){return elements[id]||(elements[id]=element(id))},
  createElement(tag){return element(tag)}
};
const context = {window:{},document,console};
for(const file of ['core/format.js','channel-registry.js','core/status.js',
  'channels/hardware.js','channels/ocpp.js','channels/github.js',
  'channels/deployments.js','channels/fleet.js']) {
  vm.runInNewContext(fs.readFileSync(path.join(root,file),'utf8'),context,{filename:file});
}
const channels = context.window.GwayMonitorChannels;
const names = ['hardware','ocpp','github','deployments','fleet'];
const registry = context.window.GwayChannelRegistry.create(names.map(x=>channels[x]),document.getElementById);
assert.equal(registry.index(-1),4);
assert.equal(registry.index(5),0);
registry.render({hardware:{available:false},ocpp:{available:false},github:null,deployments:null,fleet:null});
assert.equal(document.getElementById('ambient').textContent,'Unavailable');
assert.equal(document.getElementById('server').textContent,'Unavailable');
assert.equal(document.getElementById('pr-summary').textContent,'Unavailable');
assert.equal(document.getElementById('deployment-summary').textContent,'Deployment data unavailable');
assert.equal(document.getElementById('fleet-summary').textContent,'Fleet inventory unavailable');
for(const name of names){channels[name].mount();channels[name].unmount();}
assert.equal(channels.github.onKey(40),true);
assert.equal(channels.github.onKey(13),false);
assert.equal(channels.hardware.onKey,undefined);
const sixth = {id:'extra',title:'Extra',snapshotKey:'custom',render:x=>{context.extra=x}};
const extended = context.window.GwayChannelRegistry.create([...names.map(x=>channels[x]),sixth],document.getElementById);
assert.equal(extended.index(6),0);
extended.render({custom:42});
assert.equal(context.extra,42);
assert.throws(()=>context.window.GwayChannelRegistry.create([sixth,sixth],document.getElementById));
"""
    result = subprocess.run(
        ["node", "-e", script, str(APP)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
