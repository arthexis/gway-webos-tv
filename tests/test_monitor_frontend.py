"""B4 frontend registry and package staging characterization."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/gway-monitor"


def test_monitor_script_load_order_and_endpoint_injection_contract():
    html = (APP / "index.html").read_text()
    assert html.index('src="secret-dialog.js"') < html.index('src="channel-registry.js"')
    assert html.index('src="channel-registry.js"') < html.index('src="app.js"')
    assert (APP / "channel-registry.js").is_file()
    assert (APP / "app.js").read_text().count(
        "var url = localStorage.getItem('gway.bridge.url') || '';"
    ) == 1


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js unavailable")
def test_channel_registry_sixth_channel_and_validation():
    script = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const context = {window: {}};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const registry = context.window.GwayChannelRegistry;
const dom = {hardware: {}, 'tab-hardware': {}, extra: {}, 'tab-extra': {}};
let called = [];
const items = [
  {id: 'hardware', title: 'Hardware', render: d => called.push(['hardware', d])},
  {id: 'extra', title: 'Extra', render: d => called.push(['extra', d])}
];
const r = registry.create(items, id => dom[id]);
assert.equal(r.index(-1), 1);
assert.equal(r.index(2), 0);
r.render({hardware: 1, extra: 2});
assert.equal(called.length, 2);
assert.equal(called[1][1], 2);
assert.throws(() => registry.create([items[0], items[0]], id => dom[id]));
assert.throws(() => registry.create([{id: 'missing', title: 'Missing', render: () => {}}], id => dom[id]));
"""
    result = subprocess.run(
        ["node", "-e", script, str(APP / "channel-registry.js")],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
