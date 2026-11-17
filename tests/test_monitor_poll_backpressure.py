"""Prevent a slow monitor snapshot from queueing and delaying AP credentials."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node unavailable")
def test_wss_prioritizes_wifi_and_limits_outstanding_snapshots():
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const views={};
function el(id) {
  return views[id] || (views[id]={id,hidden:false,textContent:'',className:''});
}
const sent=[], intervals={};
let activeSocket;
class Socket {
  constructor(url) {assert.equal(url,'wss://monitor.test');this.readyState=1;activeSocket=this;}
  send(message) {sent.push(JSON.parse(message));}
  close() {this.readyState=3;}
}
Socket.OPEN=1;
const hardware={
  id:'hardware',order:0,title:'Hardware',renderWifi:()=>{},clearWifi:()=>{},
  markWifiStale:()=>{},expireWifi:()=>{},mount:()=>{},unmount:()=>{}
};
let clears=0, stales=0;
hardware.clearWifi=()=>{clears++};
hardware.markWifiStale=()=>{stales++};
const channels={hardware,
  deployments:{id:'deployments',order:3,title:'Deployments',setRetry:()=>{},mount:()=>{},unmount:()=>{}},
  ocpp:{id:'ocpp',order:1,title:'OCPP'},
  github:{id:'github',order:2,title:'GitHub'},
  fleet:{id:'fleet',order:4,title:'Fleet'}
};
const context={
  window:{
    GwayMonitorChannels:channels,
    GwayChannelRegistry:{create(items){return {index(x){return(x+items.length)%items.length},render(){}}}},
    GwaySecretDialog:{create(){return {close(){},open(){},isOpen(){return false}}}},
    scrollTo(){}
  },
  document:{getElementById:el,addEventListener(){}},
  localStorage:{getItem(key){
    return key==='gway.bridge.url'?'wss://monitor.test':
      key==='gway.monitor.credential'?'stored-pairing':null;
  },setItem(){},removeItem(){}},
  WebSocket:Socket,
  setInterval(cb,ms){intervals[ms]=cb;return ms;},
  clearInterval(){},clearTimeout(){},setTimeout(){return 1},
  console
};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
activeSocket.onopen();
activeSocket.onmessage({data:JSON.stringify({type:'ready'})});
assert.equal(sent[0].type,'auth');
assert.equal(sent[1].type,'monitor.wifi');
assert.equal(sent[2].type,'monitor.read');
for(let n=0;n<5;n++) intervals[10000]();
assert.equal(sent.filter(x=>x.type==='monitor.read').length,1);
assert.equal(sent.filter(x=>x.type==='monitor.wifi').length,1);
activeSocket.onmessage({data:JSON.stringify({
  type:'monitor.snapshot',observed_at:new Date().toISOString()
})});
intervals[10000]();
assert.equal(sent.filter(x=>x.type==='monitor.read').length,2);
activeSocket.onclose({code:1006});
assert.equal(clears,0);
assert.equal(stales,1);
"""
    result = subprocess.run(
        ["node", "-e", script, str(ROOT / "apps/gway-monitor/app.js")],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
