(function () {
  'use strict';
  var fmt = window.GwayMonitorFormat;
  var el = fmt.el, value = fmt.value, number = fmt.number, temperature = fmt.temperature;
  var duration = fmt.duration, bytes = fmt.bytes, address = fmt.address;
  var selected = 0;
  function cards() { return el('fleet-list').children; }
  function highlight(scroll) {
    var list = cards();
    if (!list.length) return;
    selected = Math.max(0, Math.min(selected, list.length - 1));
    Array.prototype.forEach.call(list, function (card, i) { card.classList.toggle('selected-card', i === selected); });
    if (scroll) {
      var viewport = el('fleet');
      var cardRect = list[selected].getBoundingClientRect();
      var viewRect = viewport.getBoundingClientRect();
      if (cardRect.bottom > viewRect.bottom) viewport.scrollTop += cardRect.bottom - viewRect.bottom;
      else if (cardRect.top < viewRect.top) viewport.scrollTop -= viewRect.top - cardRect.top;
    }
  }
  function onKey(code) {
    if (code !== 38 && code !== 40) return false;
    var list = cards();
    if (list.length) { selected = Math.max(0, Math.min(list.length - 1, selected + (code === 38 ? -1 : 1))); highlight(true); }
    return true;
  }
  function renderFleet(f) {
    var node = el('fleet-list'); node.textContent = '';
    if (!f || !f.available) { value('fleet-summary', f && f.error ? f.error : 'Fleet inventory unavailable'); return; }
    var nodes = f.nodes || [];
    value('fleet-summary', nodes.length + ' enrolled nodes · ' + (f.source || 'Watchtower'));
    if (!nodes.length) { node.textContent = 'No enrolled nodes'; return; }
    nodes.forEach(function (item) {
      var card = document.createElement('article'); card.className = 'pr-card';
      var heading = document.createElement('h2'); heading.textContent = item.node;
      var status = document.createElement('p');
      status.textContent = 'Reachability: ' + item.reachable + ' · Identity: ' + (item.identity_verified ? 'verified' : 'unverified');
      var observed = document.createElement('p'); observed.className = 'muted';
      observed.textContent = 'Last observation: ' + (item.observed_at || 'unknown');
      var telemetry = document.createElement('p'); telemetry.className = 'muted';
      var hw = item.hardware || {}, services = item.services || {}, deployments = item.deployments || {};
      var data = hw.available && hw.data && typeof hw.data === 'object' ? hw.data : null;
      var memory = data && data.memory && typeof data.memory.used_percent === 'number' ? data.memory.used_percent + '%' : 'unknown';
      var temp = data && typeof data.cpu_temperature_c === 'number' ? data.cpu_temperature_c + '°C' : 'unknown';
      var uptime = data && typeof data.uptime_seconds === 'number' ? duration(data.uptime_seconds) : 'unknown';
      telemetry.textContent = 'CPU temp: ' + temp + ' · RAM: ' + memory + ' · Uptime: ' + uptime;
      var health = document.createElement('p'); health.className = 'muted';
      var serviceList = services.available && Array.isArray(services.components) ? services.components : null;
      health.textContent = 'Services: ' + (serviceList ? serviceList.length + ' observed' : 'unknown') +
        ' · Deployments: ' + (deployments.available && Array.isArray(deployments.components) ? deployments.components.length + ' observed' : 'unknown');
      card.appendChild(heading); card.appendChild(status); card.appendChild(observed); card.appendChild(telemetry); card.appendChild(health); node.appendChild(card);
    });
    highlight(false);
  }
  window.GwayMonitorChannels = window.GwayMonitorChannels || {};
  window.GwayMonitorChannels.fleet = {id:'fleet', order:4, title:'Fleet', snapshotKey:'fleet', render:renderFleet, mount:function () { highlight(false);}, unmount:function () {}, onKey:onKey};
}());
