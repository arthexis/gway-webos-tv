import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "apps/gway-monitor/channels/images.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js unavailable")
def test_set_navigation_preserves_position_until_unmount():
    script = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const el = {'image-roll-current': {removeAttribute() {}, style: {}, classList:{remove(){}}, clientWidth:800, clientHeight:450, parentElement:{clientWidth:900,clientHeight:500}}, 'image-roll-empty': {}, 'image-roll-position': {}};
const ctx = {window: {}, document: {getElementById: id => el[id]}, setTimeout: f => f()};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const c = ctx.window.GwayMonitorChannels.images;
const item = id => ({id, filename:id+'.png', captured_at:'2026-01-01T00:00:00Z'});
const groups = [[item('new'), item('newold')], [item('old'), item('oldold')]];
let calls = []; c.setRequest(id => calls.push(id));
c.update(groups); assert.equal(calls.at(-1), 'new');
c.onKey(39); assert.equal(calls.at(-1), 'newold');
c.image('newold','data:image/jpeg;base64,YQ=='); assert.equal(el['image-roll-current'].className, 'slide-from-right');
c.onKey(40); assert.equal(calls.at(-1), 'old');
c.image('old','data:image/jpeg;base64,YQ=='); assert.equal(el['image-roll-current'].className, 'slide-from-bottom');
c.onKey(39); assert.equal(calls.at(-1), 'oldold');
c.onKey(38); assert.equal(el['image-roll-current'].className, 'slide-from-top');
c.onKey(40); assert.equal(calls.at(-1), 'oldold');
c.image('oldold','data:image/jpeg;base64,YQ==');
assert(c.onKey(13)); assert(el['image-roll-current'].style.transform.includes('scale(2)'));
assert(el['image-roll-position'].textContent.includes('ZOOM'));
c.onKey(39); assert(el['image-roll-current'].style.transform.includes('translate(-90px'));
c.onKey(40); assert(el['image-roll-current'].style.transform.includes('-90px, -90px'));
c.update(groups); assert(el['image-roll-current'].style.transform.includes('scale(2)'));
c.onKey(13); assert.equal(el['image-roll-current'].style.transform, '');
c.onKey(13); c.unmount(); assert.equal(el['image-roll-current'].style.transform, ''); c.update(groups); assert.equal(calls.at(-1), 'new');
assert(el['image-roll-position'].textContent.includes('new.png'));
assert(!el['image-roll-position'].textContent.includes('LEFT'));
"""
    result = subprocess.run(
        ["node", "-e", script, str(APP)], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
