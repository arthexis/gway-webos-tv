(function () {
  'use strict';
  var fmt = window.GwayMonitorFormat;
  var el = fmt.el, value = fmt.value, number = fmt.number, temperature = fmt.temperature;
  var duration = fmt.duration, bytes = fmt.bytes, address = fmt.address;
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
  var activeWifi = null, confirmedAt = 0;
  var WIFI_GRACE_MS = 30 * 60 * 1000;
  function clearWifi() {
    activeWifi = null;
    confirmedAt = 0;
    ['ap-ssid', 'ap-security', 'ap-password', 'ap-gateway'].forEach(function (id) { value(id, '—'); });
    value('ap-instructions', 'AP details unavailable');
    var qr = el('ap-wifi-qr');
    qr.textContent = '';
    qr.hidden = true;
  }
  function markWifiStale() {
    // Keep last verified credentials through transient bridge or NM failures.
    // Clearly label them stale, and never claim they remain current forever.
    if (!activeWifi || Date.now() - confirmedAt > WIFI_GRACE_MS) {
      clearWifi();
      return;
    }
    value('ap-instructions', 'Last confirmed network · reconnecting');
  }
  function expireWifi() {
    if (activeWifi && Date.now() - confirmedAt > WIFI_GRACE_MS) clearWifi();
  }
  function qrSvg(rows) {
    if (!Array.isArray(rows) || rows.length < 21 || rows.length > 185) return null;
    var size = rows.length, path = [];
    for (var y = 0; y < size; y++) {
      if (typeof rows[y] !== 'string' || rows[y].length !== size || !/^[01]+$/.test(rows[y])) return null;
      for (var x = 0; x < size; x++) {
        if (rows[y].charAt(x) === '1') path.push('M' + x + ' ' + y + 'h1v1h-1z');
      }
    }
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 ' + size + ' ' + size);
    svg.setAttribute('shape-rendering', 'crispEdges');
    svg.setAttribute('aria-hidden', 'true');
    var white = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    white.setAttribute('width', String(size)); white.setAttribute('height', String(size));
    white.setAttribute('fill', '#fff');
    var pixels = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    pixels.setAttribute('fill', '#000'); pixels.setAttribute('d', path.join(''));
    svg.appendChild(white); svg.appendChild(pixels);
    return svg;
  }
  function renderWifi(wifi) {
    if (!wifi || wifi.available !== true || typeof wifi.ssid !== 'string' ||
        typeof wifi.password !== 'string' || typeof wifi.gateway !== 'string' ||
        typeof wifi.security !== 'string') {
      markWifiStale();
      return;
    }
    var signature = JSON.stringify([wifi.ssid, wifi.security, wifi.password, wifi.gateway, wifi.portal_url]);
    if (signature !== activeWifi) {
      // Build and validate the new QR before touching the existing DOM.
      var graphic = qrSvg(wifi.qr);
      if (!graphic) { markWifiStale(); return; }
      value('ap-ssid', wifi.ssid);
      value('ap-security', wifi.security);
      value('ap-password', wifi.password);
      value('ap-gateway', 'Portal: ' + (typeof wifi.portal_url === 'string' ? wifi.portal_url : 'http://' + wifi.gateway));
      var node = el('ap-wifi-qr');
      node.textContent = '';
      node.appendChild(graphic);
      node.hidden = false;
      node.setAttribute('aria-label', 'Scan to join Wi-Fi ' + wifi.ssid);
      activeWifi = signature;
    }
    confirmedAt = Date.now();
    value('ap-instructions', 'Scan to join · registration required for Internet');
  }
  window.GwayMonitorChannels = window.GwayMonitorChannels || {};
  window.GwayMonitorChannels.hardware = {id:'hardware', order:0, title:'Hardware', snapshotKey:'hardware', render:renderHardware, renderWifi:renderWifi, clearWifi:clearWifi, markWifiStale:markWifiStale, expireWifi:expireWifi, mount:function () {}, unmount:function () {}};
}());
