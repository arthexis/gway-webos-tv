(function () {
  'use strict';
  var url = localStorage.getItem('gway.bridge.url') || '';
  var credential = localStorage.getItem('gway.monitor.credential') || '';
  var socket = null, ready = false, retry = null, poll = null, channel = 0;
  var lastObserved = 0, lastReceived = 0;
  var retryJobs = {}, retryTimer = null;
  function send(message) { if (!ready || !socket || socket.readyState !== WebSocket.OPEN) return false; socket.send(JSON.stringify(message)); return true; }
  window.GwayMonitorChannels.deployments.setRetry(function (name) {
    if (retryJobs[name] || !send({type:'deployment.retry', name:name})) return false;
    retryJobs[name] = true;
    return true;
  });
  function pollRetries() {
    Object.keys(retryJobs).forEach(function (name) { send({type:'deployment.retry.status', name:name}); });
  }
  retryTimer = setInterval(pollRetries, 3000);
  var dialog = window.GwaySecretDialog.create({
    onSubmit: function (secret) { connect(secret); },
    onCancel: function () { showConnection('Disconnected'); }
  });
  function el(id) { return document.getElementById(id); }
  function value(id, text) { el(id).textContent = text === null || text === undefined || text === '' ? '—' : String(text); }
  function showConnection(text) { value('connection', text); el('reconnect-hint').hidden = ready; }
  var channels = Object.keys(window.GwayMonitorChannels).map(function (id) {
    return window.GwayMonitorChannels[id];
  }).sort(function (a, b) { return a.order - b.order; });
  var registry = window.GwayChannelRegistry.create(channels, function (id) { return document.getElementById(id); });
  function switchChannel(next) {
    var previous = channels[channel];
    if (previous && typeof previous.unmount === 'function') previous.unmount();
    channel = registry.index(next);
    channels.forEach(function (item, i) {
      el(item.id).hidden = channel !== i;
      el('tab-' + item.id).className = channel === i ? 'selected' : '';
    });
    value('title', channels[channel].title);
    value('channel-count', channels[channel].footerText || '');
    window.scrollTo(0, 0);
    if (typeof channels[channel].mount === 'function') channels[channel].mount();
  }
  function render(msg) {
    if (!msg || msg.type !== 'monitor.snapshot') return;
    var timestamp = Date.parse(msg.observed_at);
    if (!isFinite(timestamp) || timestamp > Date.now() + 60000) {
      value('freshness', 'Invalid observation time'); return;
    }
    lastObserved = timestamp; lastReceived = Date.now();
    registry.render(msg); updateFreshness();
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
      else if (msg.type === 'deployment.retry.started' || msg.type === 'deployment.retry.running') {
        if (typeof msg.name === 'string') { retryJobs[msg.name] = true; channels.filter(function (c) { return c.id === 'deployments'; })[0].retryState(msg.name, 'running'); }
      } else if (msg.type === 'deployment.retry.result') {
        if (typeof msg.name === 'string') {
          delete retryJobs[msg.name];
          channels.filter(function (c) { return c.id === 'deployments'; })[0].retryState(msg.name, 'done', msg.error || null);
          request();
        }
      }
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
    if (code === 33 || code === 34) { event.preventDefault(); switchChannel(channel + (code === 33 ? 1 : -1)); return; }
    if (typeof channels[channel].onKey === 'function' && channels[channel].onKey(code)) { event.preventDefault(); return; }
    if (!ready && code === 13 && url) { event.preventDefault(); dialog.open(); }
  });
  switchChannel(0);
  if (url && credential) connect('');
  else if (url) dialog.open();
  else showConnection('Bridge not configured');
  setInterval(updateFreshness, 1000);
}());
