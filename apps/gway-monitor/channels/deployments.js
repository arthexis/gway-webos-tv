(function () {
  'use strict';
  var fmt = window.GwayMonitorFormat;
  var el = fmt.el, value = fmt.value, number = fmt.number, temperature = fmt.temperature;
  var duration = fmt.duration, bytes = fmt.bytes, address = fmt.address;
  var selected = 0;
  function cards() { return el('deployment-list').children; }
  function highlight(scroll) {
    var list = cards();
    if (!list.length) return;
    selected = Math.max(0, Math.min(selected, list.length - 1));
    Array.prototype.forEach.call(list, function (card, i) { card.classList.toggle('selected-card', i === selected); });
    if (scroll) {
      var viewport = el('deployments');
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
  function renderDeployments(d) {
    var node = el('deployment-list'); node.textContent = '';
    if (!d || !d.available) { value('deployment-summary', 'Deployment data unavailable'); window.GwayMonitorChannels.deployments.footerText = 'Deployments unavailable'; if (!el('deployments').hidden) value('channel-count', 'Deployments unavailable'); return; }
    var items = d.components || [];
    var countText = items.length + ' deployments · ' + (d.node || 'gway-001');
    window.GwayMonitorChannels.deployments.footerText = countText;
    if (!el('deployments').hidden) value('channel-count', countText);
    value('deployment-summary', items.length + ' configured components on ' + (d.node || 'gway-001'));
    if (!items.length) { node.textContent = 'No configured components reported'; return; }
    items.forEach(function (item) {
      var card = document.createElement('article'); card.className = 'pr-card';
      var heading = document.createElement('h2'); heading.textContent = item.repository || item.name;
      var detail = document.createElement('p');
      var parsed = item.deployed_at ? new Date(item.deployed_at) : null;
      var dateText = parsed && !isNaN(parsed.getTime()) ? parsed.toLocaleString() : 'Date unavailable';
      detail.textContent = 'Revision: ' + (item.revision || 'unknown') + ' · Deployed: ' + dateText;
      var state = document.createElement('p'); state.className = 'muted';
      state.textContent = 'Install: ' + item.installation + ' · Health: ' + item.health + (item.error ? ' · Evidence: ' + item.error : '');
      var text = document.createElement('div'); text.className = 'status-copy';
      text.appendChild(heading); text.appendChild(detail); text.appendChild(state);
      card.appendChild(text); card.appendChild(window.GwayMonitorStatus.badge(window.GwayMonitorStatus.deployment(item))); node.appendChild(card);
    });
    highlight(false);
  }
  window.GwayMonitorChannels = window.GwayMonitorChannels || {};
  window.GwayMonitorChannels.deployments = {id:'deployments', order:3, title:'Deployments', snapshotKey:'deployments', render:renderDeployments, mount:function () { highlight(false);}, unmount:function () {}, onKey:onKey};
}());
