'use strict';
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
let listener;
const label = {textContent: ''};
const overlay = {hidden: false, className: '', innerHTML: '', querySelector: () => label};
const document = {
  createElement: () => overlay,
  body: {appendChild: () => {}},
  addEventListener: (type, callback, capture) => { assert.strictEqual(type, 'keydown'); assert.strictEqual(capture, true); listener = callback; }
};
const window = {};
vm.runInNewContext(fs.readFileSync('apps/remote-test/secret-dialog.js', 'utf8'), {window, document});
let result;
const dialog = window.GwaySecretDialog.create({onSubmit: value => { result = value; }});
function press(code) {
  let prevented = false;
  let stopped = false;
  listener({keyCode: code, preventDefault: () => { prevented = true; }, stopImmediatePropagation: () => { stopped = true; }});
  assert(prevented && stopped);
}
dialog.open();
press(48); press(49); press(50); press(461); press(50); press(51); press(52); press(53);
assert(!label.textContent.includes('012345'));
press(13);
assert.strictEqual(result, '012345');
assert(!dialog.isOpen());
assert(!label.textContent.includes('012345'));
console.log('Remote secret dialog test passed');
