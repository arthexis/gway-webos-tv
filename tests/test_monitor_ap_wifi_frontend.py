"""Chromium-compatible TV AP panel, reset and local-only QR rendering."""
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "apps/gway-monitor"


def test_hardware_lower_right_layout_and_existing_channels():
    html = (APP / "index.html").read_text()
    css = (APP / "style.css").read_text()
    assert html.index('id="ap-wifi-qr"') > html.index('id="wlan1"')
    assert html.index('id="ap-wifi-qr"') < html.index('id="ocpp"')
    assert 'class="ap-connect"' in html
    assert "#hardware .ap-connect{grid-column:3;grid-row:2/span 2" in css
    assert "width:174px;height:174px" in css
    assert "padding:3vh 2vw" in css
    assert 'src="channels/hardware.js"' in html
    assert 'id="tab-github"' in html


@pytest.mark.skipif(shutil.which("node") is None, reason="Node unavailable")
def test_qr_rendering_no_html_injection_and_clear_on_unavailable():
    script = r"""
const assert = require('assert'), fs = require('fs'), vm = require('vm');
const map = {};
function element(tag, id) {
  const node = {
    tag, id, hidden:true, children:[], attrs:{},
    appendChild(x){this.children.push(x)},
    setAttribute(key,val){this.attrs[key]=val},
  };
  let text = '';
  Object.defineProperty(node,'textContent',{
    get(){return text},
    set(value){text=value;node.children=[]}
  });
  return node;
}
const document = {
  getElementById(id){return map[id] || (map[id]=element('div',id))},
  createElementNS(ns,tag){assert.equal(ns,'http://www.w3.org/2000/svg');return element(tag)}
};
const format={el:document.getElementById, value(id,v){document.getElementById(id).textContent=v},
  number(){},temperature(){},duration(){},bytes(){},address(){}};
let now=100000;
const ctx={window:{GwayMonitorFormat:format},document,Date:{now:()=>now}};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'),ctx);
const hw=ctx.window.GwayMonitorChannels.hardware;
const rows=Array.from({length:29},(_,i)=>Array.from({length:29},(_,j)=>(i*j)%3===0?'1':'0').join(''));
const secret='<img src=x onerror=alert(1)>';
hw.renderWifi({available:true,ssid:'Office Wi-Fi',security:'WPA2',password:secret,
   gateway:'10.42.0.1',portal_url:'http://10.42.0.1',qr:rows});
assert.equal(map['ap-password'].textContent,secret);
assert.equal(map['ap-ssid'].textContent,'Office Wi-Fi');
assert.equal(map['ap-wifi-qr'].hidden,false);
assert.equal(map['ap-wifi-qr'].children.length,1);
const svg=map['ap-wifi-qr'].children[0];
assert.equal(svg.attrs.viewBox,'0 0 29 29');
assert.equal(svg.children[0].tag,'rect');
assert.equal(svg.children[1].tag,'path');
assert(svg.children[1].attrs.d.length>100);
hw.renderWifi({available:true,ssid:'Office Wi-Fi',security:'WPA2',password:secret,
   gateway:'10.42.0.1',portal_url:'http://10.42.0.1',qr:rows});
assert.strictEqual(map['ap-wifi-qr'].children[0],svg); // unchanged: no DOM rewrite
hw.markWifiStale();
assert.equal(map['ap-wifi-qr'].hidden,false);
assert(map['ap-instructions'].textContent.includes('Last confirmed'));
hw.unmount();
assert.equal(map['ap-wifi-qr'].hidden,false); // hidden tab, not deleted
hw.renderWifi({available:true,ssid:'Office Wi-Fi',security:'WPA2',password:secret,
   gateway:'10.42.0.1',portal_url:'http://10.42.0.1',qr:rows});
assert.strictEqual(map['ap-wifi-qr'].children[0],svg);
assert(map['ap-instructions'].textContent.includes('Scan to join'));
now += 31*60*1000;
hw.expireWifi();
assert.equal(map['ap-wifi-qr'].hidden,true);
hw.renderWifi({available:true,ssid:'Office Wi-Fi',security:'WPA2',password:secret,
   gateway:'10.42.0.1',portal_url:'http://10.42.0.1',qr:rows});
assert.equal(map['ap-wifi-qr'].hidden,false);
hw.clearWifi();
assert.equal(map['ap-password'].textContent,'—');
assert.equal(map['ap-wifi-qr'].hidden,true);
assert.equal(map['ap-wifi-qr'].children.length,0); // textContent clears children
hw.renderWifi({available:false});
assert.equal(map['ap-wifi-qr'].hidden,true);
hw.renderWifi({available:true,ssid:'x',security:'WPA2',password:'abc',
 gateway:'10.42.0.1',qr:['X']});
assert.equal(map['ap-wifi-qr'].hidden,true);
"""
    result = subprocess.run(
        ["node", "-e", script, str(APP / "channels/hardware.js")],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_wifi_key_not_stored_in_localstorage_or_snapshot():
    code = (APP / "app.js").read_text()
    assert "monitor.wifi" in code
    assert "requestWifi(false)" in code
    assert "lastWifiRequested < 300000" in code
    assert "channels[0].markWifiStale()" in code
    assert "channels[0].expireWifi()" in code
    assert "if (event.code === 1008) channels[0].clearWifi()" in code
    assert code.index("requestWifi(false);", code.index("  function request()")) < code.index("monitor.read", code.index("  function request()"))
    assert "localStorage.setItem('gway.wifi" not in code
    assert "console.log" not in (APP / "channels/hardware.js").read_text()
    bridge = (
        Path(__file__).resolve().parents[1] / "src/gway_webos_tv/event_bridge.py"
    ).read_text()
    assert 'data.get("type") == "monitor.wifi"' in bridge
    assert "await asyncio.to_thread(wifi_message)" in bridge
