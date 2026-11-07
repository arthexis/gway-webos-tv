"""Regression tests for channel-only scrolling and deployment timestamps."""
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/gway-monitor"


def test_viewport_css_keeps_header_and_navigation_visible():
    css = (APP / "style.css").read_text()
    assert "main{height:100vh" in css
    assert "main>header,main>nav,main>footer{flex:0 0 auto}" in css
    assert "main>section{flex:1 1 auto;min-height:0;overflow-y:auto" in css
    assert "padding:3vh 2vw" in css


@pytest.mark.skipif(shutil.which("node") is None, reason="Node unavailable")
@pytest.mark.parametrize("channel,list_id", [
    ("github", "pr-list"), ("deployments", "deployment-list"), ("fleet", "fleet-list"),
])
def test_arrows_scroll_only_channel_viewport(channel, list_id):
    script = r"""
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const channel=process.argv[2],listId=process.argv[3],nodes={};
function el(id) {
 if(!nodes[id]) nodes[id]={children:[],scrollTop:0,
  getBoundingClientRect(){return {top:100,bottom:400}},
  classList:{toggle(){}},textContent:''};
 return nodes[id];
}
const ctx={window:{GwayMonitorChannels:{},GwayMonitorFormat:{el,value(){}}},document:{createElement(){return {appendChild(){},classList:{toggle(){}},getBoundingClientRect(){return {top:390,bottom:520}}}}}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
const c=ctx.window.GwayMonitorChannels[channel];
el(listId).children=[{classList:{toggle(){}},getBoundingClientRect(){return {top:390,bottom:520}},
 scrollIntoView(){throw Error('document scroll must never be used')}}];
assert.equal(c.onKey(40),true);
assert.equal(el(channel).scrollTop,120);
assert.equal(c.onKey(38),true);
assert.equal(el(channel).scrollTop,240);
assert.equal(c.onKey(13),false);
"""
    result = subprocess.run(["node", "-e", script, str(APP / "channels" / (channel + ".js")), channel, list_id],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_deployment_timestamp_is_not_observation_timestamp():
    from gway_webos_tv import deployment_monitor
    sample = {"checked_at": "2026-11-07T01:00:00Z", "components": [
        {"name": "first", "deployment_evidence": {"activated_revision": "abc",
            "observed_at": "2026-11-07T01:00:00Z", "activated_at": "2026-10-31T20:00:00Z"}},
        {"name": "second", "deployment_evidence": {"observed_at": "2026-11-07T01:00:00Z"}},
    ]}
    with patch.object(deployment_monitor, "read_json", return_value=sample):
        result = deployment_monitor.snapshot()
    assert result["components"][0]["deployed_at"] == "2026-10-31T20:00:00Z"
    assert result["components"][1]["deployed_at"] is None
