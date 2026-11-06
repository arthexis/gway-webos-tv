'use strict';
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const elements = {};
for (const id of ['name', 'code', 'detail', 'bridge-status', 'bridge-hint']) elements[id] = {textContent: '', hidden: false};
const list = {children: [], insertBefore(item) { this.children.unshift(item); }, removeChild(item) { this.children.splice(this.children.indexOf(item), 1); }, get firstElementChild() { return this.children[0]; }, get firstChild() { return this.children[0]; }, get lastChild() { return this.children[this.children.length - 1]; }};
elements.events = list;
let keyHandler, socket;
const document = {getElementById: id => elements[id], createElement: () => ({textContent: ''}), addEventListener: (type, handler) => { if (type === 'keydown') keyHandler = handler; }};
const localStorage = {getItem: key => key.endsWith('.url') ? 'wss://example.test' : 'test-credential', setItem() {}, removeItem() {}};
function WebSocket() { socket = this; this.send = data => { this.last = JSON.parse(data); }; this.close = () => {}; }
const window = {GwaySecretDialog: {create: () => ({open() {}, close() {}})}};
vm.runInNewContext(fs.readFileSync('apps/remote-test/app.js', 'utf8'), {window, document, localStorage, WebSocket, setTimeout() {}, clearTimeout() {}});
socket.onopen();
socket.onmessage({data: JSON.stringify({type: 'ready'})});
function press(code, key) { keyHandler({target: {tagName: 'BODY'}, keyCode: code, key, code: key, preventDefault() {}}); }
function acknowledge(name) { socket.onmessage({data: JSON.stringify({type: 'button.accepted', code: socket.last.code, id: socket.last.id, name})}); }
press(13, 'Enter'); acknowledge('OK'); assert.strictEqual(elements.name.textContent, 'OK'); assert(list.children[0].textContent.startsWith('OK  ·'));
press(415, 'Unidentified'); acknowledge(null); assert.strictEqual(elements.name.textContent, 'Play');
press(1011, 'Unidentified'); acknowledge('Fav'); assert.strictEqual(elements.name.textContent, 'Fav');
press(1011, 'Unidentified'); acknowledge(null); assert.strictEqual(elements.name.textContent, 'Unidentified');
console.log('Remote button name test passed');
