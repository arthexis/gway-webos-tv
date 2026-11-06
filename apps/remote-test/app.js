(function () {
  'use strict';
  var names = {13: 'OK / Enter', 19: 'Pause', 37: 'Left', 38: 'Up', 39: 'Right', 40: 'Down', 403: 'Red', 404: 'Green', 405: 'Yellow', 406: 'Blue', 412: 'Rewind', 413: 'Stop', 415: 'Play', 417: 'Fast forward', 461: 'Back'};
  var list = document.getElementById('events');
  var overrides = {}, pending = {}, sequence = 0, lastCode = null;
  var socket = null, ready = false, retry = null;
  var status = document.getElementById('bridge-status');
  var hint = document.getElementById('bridge-hint');
  // URL is injected when packaging for a deployment and never shown in the UI.
  var url = localStorage.getItem('gway.bridge.url') || '';
  var credential = localStorage.getItem('gway.bridge.credential') || '';
  var dialog = window.GwaySecretDialog.create({onSubmit: function (code) { connect(code); }, onCancel: function () { status.textContent = 'Disconnected'; }});
  function connect(pairing) {
    var attemptedPair = Boolean(pairing);
    if (retry) clearTimeout(retry);
    if (socket) { socket.onclose = null; socket.close(); }
    ready = false;
    if (!/^wss:\/\//i.test(url)) { status.textContent = 'Bridge not configured'; return; }
    status.textContent = 'Connecting';
    try { socket = new WebSocket(url); } catch (_) { status.textContent = 'Connection failed'; return; }
    socket.onopen = function () {
      if (pairing) { socket.send(JSON.stringify({type: 'pair', secret: pairing})); pairing = ''; }
      else if (credential) socket.send(JSON.stringify({type: 'auth', credential: credential}));
      else socket.close();
    };
    socket.onmessage = function (event) {
      var msg; try { msg = JSON.parse(event.data); } catch (_) { return; }
      if (msg.type === 'paired' && typeof msg.credential === 'string') {
        credential = msg.credential; localStorage.setItem('gway.bridge.url', url);
        localStorage.setItem('gway.bridge.credential', credential); ready = true;
      } else if (msg.type === 'ready') ready = true;
      else if (msg.type === 'button.accepted' && typeof msg.code === 'number') {
        if (typeof msg.name === 'string' && msg.name) overrides[msg.code] = msg.name;
        else delete overrides[msg.code];
        var entry = pending[msg.id];
        if (entry) {
          var label = overrides[msg.code] || names[msg.code] || entry.fallback;
          entry.element.textContent = label + '  ·  ' + msg.code + '  ·  ' + entry.details;
          delete pending[msg.id];
        }
        if (lastCode === msg.code) document.getElementById('name').textContent = overrides[msg.code] || names[msg.code] || (entry ? entry.fallback : 'Unknown');
      }
      if (ready) { status.textContent = 'Connected'; hint.hidden = true; dialog.close(); }
    };
    socket.onclose = function (event) {
      pairing = '';
      ready = false; status.textContent = 'Disconnected'; hint.hidden = false;
      if (event.code === 1008 && attemptedPair) status.textContent = 'Pairing rejected';
      if (event.code === 1008 && !attemptedPair) { credential = ''; localStorage.removeItem('gway.bridge.credential'); }
      if (credential) retry = setTimeout(function () { connect(''); }, 5000);
    };
    socket.onerror = function () { status.textContent = 'Connection failed'; };
  }
  if (url && credential) connect('');
  else if (url) dialog.open();
  document.addEventListener('keydown', function (event) {
    if (/^(INPUT|BUTTON|TEXTAREA)$/.test(event.target.tagName)) return;
    var code = event.keyCode || event.which || 0;
    if (!ready && code === 13 && url) { event.preventDefault(); dialog.open(); return; }
    var send = ready && code > 0 && code <= 65535 && !event.repeat;
    var id = send ? ++sequence : null;
    var fallback = event.key || 'Unknown';
    var name = overrides[code] || names[code] || fallback;
    var details = 'key: ' + (event.key || 'unavailable') + ' · code: ' + (event.code || 'unavailable') + (event.repeat ? ' · repeat' : '');
    lastCode = code;
    document.getElementById('name').textContent = name;
    document.getElementById('code').textContent = code || '—';
    document.getElementById('detail').textContent = details;
    if (list.firstElementChild && list.firstElementChild.className === 'empty') list.removeChild(list.firstElementChild);
    var item = document.createElement('li');
    item.textContent = name + '  ·  ' + code + '  ·  ' + details;
    if (id !== null) { item.gwayEventId = id; pending[id] = {element: item, details: details, fallback: fallback}; }
    list.insertBefore(item, list.firstChild);
    while (list.children.length > 5) { delete pending[list.lastChild.gwayEventId]; list.removeChild(list.lastChild); }
    if (send) socket.send(JSON.stringify({type: 'button.pressed', code: code, id: id}));
  });
}());
