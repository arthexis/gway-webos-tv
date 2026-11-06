(function () {
  'use strict';
  var url = localStorage.getItem('gway.bridge.url') || '';
  var credential = localStorage.getItem('gway.monitor.credential') || '';
  var socket = null, ready = false, retry = null, poll = null, channel = 0;
  var lastObserved = 0, lastReceived = 0;
  var dialog = window.GwaySecretDialog.create({
    onSubmit: function (secret) { connect(secret); },
    onCancel: function () { showConnection('Disconnected'); }
  });
  function el(id) { return document.getElementById(id); }
  function value(id, text) { el(id).textContent = text === null || text === undefined || text === '' ? '—' : String(text); }
  function showConnection(text) { value('connection', text); el('reconnect-hint').hidden = ready; }
  function number(n, suffix) { return typeof n === 'number' && isFinite(n) ? n.toFixed(1) + (suffix || '') : '—'; }
  function temperature(n) { return number(n, ' °C'); }
  function duration(seconds) {
    if (typeof seconds !== 'number' || seconds < 0) return '—';
    return Math.floor(seconds / 86400) + 'd ' + Math.floor(seconds % 86400 / 3600) + 'h';
  }
  function bytes(n) { return typeof n === 'number' && n >= 0 ? (n / 1073741824).toFixed(1) + ' GiB' : '—'; }
  function address(info) {
    if (!info || info.present !== true) return 'Not installed';
    if (info.up !== true) return 'Down';
    if (!Array.isArray(info.ipv4) || !info.ipv4.length) return 'No IPv4 address';
    return info.ipv4.join(', ');
  }
  function switchChannel(next) {
    channel = next;
    el('hardware').hidden = channel !== 0;
    el('ocpp').hidden = channel !== 1;
    el('tab-hardware').className = channel === 0 ? 'selected' : '';
    el('tab-ocpp').className = channel === 1 ? 'selected' : '';
    value('title', channel === 0 ? 'Hardware' : 'OCPP');
  }
  function renderHardware(h) {
    if (!h || h.available !== true) {
      ['ambient', 'soc', 'model', 'uptime', 'memory', 'disk', 'disk-free', 'eth0', 'wlan0', 'wlan1'].forEach(function (id) { value(id, 'Unavailable'); });
      return;
    }
    value('ambient', temperature(h.ambient_c));
    value('soc', temperature(h.soc_c));
    value('model', h.model);
    value('uptime', duration(h.uptime_seconds));
    var memory = h.memory || {}, disk = h.disk || {};
    value('memory', typeof memory.used_percent === 'number' ? number(memory.used_percent, '% used') : '—');
    value('disk', typeof disk.used_percent === 'number' ? number(disk.used_percent, '% used') : '—');
    value('disk-free', 'Free: ' + bytes(disk.free_bytes));
    var ips = h.interfaces || {};
    ['eth0', 'wlan0', 'wlan1'].forEach(function (id) { value(id, address(ips[id])); });
  }
  function renderTransaction(tx, label) {
    value('tx-title', label);
    var node = el('tx-content');
    node.textContent = '';
    if (!tx) { node.textContent = 'No recorded transaction'; return; }
    [['Charger', tx.charger_id], ['Connector', tx.connector_id], ['State', tx.state],
      ['Started', tx.started_at], ['Stopped', tx.stopped_at],
      ['Energy', typeof tx.energy_wh === 'number' ? number(tx.energy_wh / 1000, ' kWh') : null]]
      .forEach(function (entry) {
        var item = document.createElement('div'), title = document.createElement('span'), data = document.createElement('strong');
        item.className = 'tx-row'; title.textContent = entry[0]; data.textContent = entry[1] == null ? '—' : String(entry[1]);
        item.appendChild(title); item.appendChild(data); node.appendChild(item);
      });
  }
  function renderOcpp(o) {
    if (!o || o.available !== true) {
      value('server', 'Unavailable'); value('storage', 'CSMS status unavailable');
      value('chargers', '—'); value('tx-title', 'Current / last transaction');
      value('tx-content', 'Transaction data unavailable'); return;
    }
    value('server', o.server && typeof o.server.state === 'string' ? o.server.state : 'Unknown');
    value('storage', o.storage && typeof o.storage.database === 'string' ? 'Database: ' + o.storage.database + ' · Transactions: ' + (o.storage.transactions || 'unknown') : 'Storage unavailable');
    value('chargers', String(o.connected_count || 0) + ' / ' + String(o.charger_count || 0));
    if (!o.active_query_ok || !o.last_query_ok) {
      value('tx-content', 'Transaction query unavailable');
      value('tx-title', 'Current / last transaction');
    } else if (o.current) renderTransaction(o.current, 'Current transaction (recorded)');
    else renderTransaction(o.last, 'Last transaction (recorded)');
  }
  function render(msg) {
    if (!msg || msg.type !== 'monitor.snapshot') return;
    var timestamp = Date.parse(msg.observed_at);
    if (!isFinite(timestamp) || timestamp > Date.now() + 60000) {
      value('freshness', 'Invalid observation time'); return;
    }
    lastObserved = timestamp; lastReceived = Date.now();
    renderHardware(msg.hardware); renderOcpp(msg.ocpp); updateFreshness();
  }
  function updateFreshness() {
    if (!lastReceived) { value('freshness', 'Waiting for data'); return; }
    var age = Math.max(0, Math.floor((Date.now() - lastObserved) / 1000));
    value('freshness', (age > 30 ? 'Stale data · ' : 'Updated · ') + age + 's ago');
  }
  function request() {
    if (ready && socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({type: 'monitor.read'}));
    updateFreshness();
  }
  function connect(secret) {
    if (retry) clearTimeout(retry);
    if (poll) clearInterval(poll);
    if (socket) { socket.onclose = null; socket.close(); }
    ready = false;
    if (!/^wss:\/\//i.test(url)) { showConnection('Bridge not configured'); return; }
    showConnection('Connecting');
    try { socket = new WebSocket(url); } catch (_) { showConnection('Connection failed'); return; }
    socket.onopen = function () {
      if (secret) socket.send(JSON.stringify({type: 'pair', secret: secret, app: 'gway-monitor'}));
      else if (credential) socket.send(JSON.stringify({type: 'auth', credential: credential}));
      else socket.close();
      secret = '';
    };
    socket.onmessage = function (event) {
      var msg;
      try { msg = JSON.parse(event.data); } catch (_) { return; }
      if (msg.type === 'paired' && typeof msg.credential === 'string') {
        credential = msg.credential; localStorage.setItem('gway.monitor.credential', credential);
        localStorage.setItem('gway.bridge.url', url);
      }
      if (msg.type === 'paired' || msg.type === 'ready') {
        ready = true; showConnection('Connected'); dialog.close();
        request(); poll = setInterval(request, 10000);
      } else if (msg.type === 'monitor.snapshot') render(msg);
    };
    socket.onclose = function (event) {
      ready = false; showConnection(event.code === 1008 ? 'Authorization rejected' : 'Disconnected');
      if (poll) clearInterval(poll);
      if (event.code === 1008) { credential = ''; localStorage.removeItem('gway.monitor.credential'); }
      else if (credential) retry = setTimeout(function () { connect(''); }, 5000);
    };
    socket.onerror = function () { showConnection('Connection failed'); };
  }
  document.addEventListener('keydown', function (event) {
    if (dialog.isOpen()) return;
    var code = event.keyCode || event.which;
    if (code === 33 || code === 34) { switchChannel(code === 33 ? 0 : 1); return; }
    if (!ready && code === 13 && url) { event.preventDefault(); dialog.open(); }
  });
  switchChannel(0);
  if (url && credential) connect('');
  else if (url) dialog.open();
  else showConnection('Bridge not configured');
  setInterval(updateFreshness, 1000);
}());
