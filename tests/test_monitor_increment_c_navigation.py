"""Exercise monitor transport and remote key routing without a real TV."""
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "apps" / "gway-monitor"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node unavailable")
def test_page_navigation_pairing_and_channel_keys():
    script = r"""
const fs=require('fs'),vm=require('vm'),path=require('path'),assert=require('assert');
const root=process.argv[1],listeners={};
const nodes={};
function node(id){return nodes[id]||(nodes[id]={
  id,hidden:false,className:'',textContent:'',children:[],
  classList:{toggle(){}},appendChild(x){this.children.push(x)},scrollIntoView(){}
});}
const store={};
const ctx={
 window:{scrollTo(){}}, document:{
  getElementById:node,createElement:node,
  addEventListener(type,cb){listeners[type]=cb}
 },
 localStorage:{getItem(k){return store[k]||null},setItem(k,v){store[k]=v},removeItem(k){delete store[k]}},
 setInterval(){return 1},clearInterval(){},setTimeout(){return 2},clearTimeout(){},
 Date,JSON,WebSocket:{OPEN:1},console
};
ctx.window.GwaySecretDialog={create(){return {
 isOpen(){return false},open(){},close(){}
}}};
for(const name of ['core/format.js','channel-registry.js',
 'channels/hardware.js','channels/ocpp.js','channels/github.js',
 'channels/deployments.js','channels/fleet.js','app.js']){
 vm.runInNewContext(fs.readFileSync(path.join(root,name),'utf8'),ctx,{filename:name});
}
assert.equal(node('hardware').hidden,false);
assert.equal(node('ocpp').hidden,true);
function key(code){let prevented=false;listeners.keydown({keyCode:code,preventDefault(){prevented=true}});return prevented}
assert(key(34));
assert.equal(node('ocpp').hidden,false);
assert(key(33));
assert.equal(node('hardware').hidden,false);
assert(key(33));
assert.equal(node('fleet').hidden,false);
assert(key(40));
assert.equal(node('fleet').hidden,false);
assert.equal(key(13),false);
"""
    result = subprocess.run(
        ["node", "-e", script, str(APP)], capture_output=True,
        text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr
