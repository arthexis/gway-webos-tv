(function () {
  'use strict';
  var el = window.GwayMonitorFormat.el, value = window.GwayMonitorFormat.value;
  var status = window.GwayMonitorStatus;
  var selected = 0, items = [], active = {}, errors = {};
  var retry = function () { return false; };
  function setRetry(fn) { retry = fn; }
  function retryState(name, phase, error) {
    if (phase === 'running') { active[name] = true; delete errors[name]; }
    else { delete active[name]; if (error) errors[name] = error; else delete errors[name]; }
    if (window.GwayMonitorChannels.deployments.lastSnapshot) renderDeployments(window.GwayMonitorChannels.deployments.lastSnapshot);
  }
  function columns() {
    // Match the CSS breakpoint exactly. Use a narrow fallback in node-only tests.
    if (typeof window.matchMedia === 'function') return window.matchMedia('(min-width: 1200px)').matches ? 2 : 1;
    return typeof window.innerWidth === 'number' && window.innerWidth >= 1200 ? 2 : 1;
  }
  function cards() { return el('deployment-list').children; }
  function highlight(scroll) {
    var list = cards();
    if (!list.length) { selected = 0; return; }
    selected = Math.max(0, Math.min(selected, list.length - 1));
    Array.prototype.forEach.call(list, function (card, i) {
      card.classList.toggle('selected-card', i === selected);
      if (typeof card.setAttribute === 'function') card.setAttribute('aria-current', i === selected ? 'true' : 'false');
    });
    if (scroll) {
      var viewport = el('deployments'), cardRect = list[selected].getBoundingClientRect(), viewRect = viewport.getBoundingClientRect();
      if (cardRect.bottom > viewRect.bottom) viewport.scrollTop += cardRect.bottom - viewRect.bottom;
      else if (cardRect.top < viewRect.top) viewport.scrollTop -= viewRect.top - cardRect.top;
    }
  }
  function onKey(code) {
    if (code === 13) {
      var item = items[selected];
      if (!item) return true;
      if (!active[item.name] && status.deployment(item).level === 'failed' && retry(item.name)) retryState(item.name, 'running');
      return true;
    }
    if (code !== 37 && code !== 38 && code !== 39 && code !== 40) return false;
    var list = cards();
    if (!list.length) return true;
    var two = columns() === 2, next = selected;
    if (code === 38) next -= two ? 2 : 1;
    if (code === 40) next += two ? 2 : 1;
    if (code === 37 && two && selected % 2 === 1) next--;
    if (code === 39 && two && selected % 2 === 0 && selected + 1 < list.length) next++;
    if ((code === 37 || code === 39) && !two) return false;
    // A partial final row has no corresponding cell in the other row.
    // Clamping ±2 to the list endpoint would move diagonally between columns.
    if (two && (code === 38 || code === 40) &&
        (next < 0 || next >= list.length)) next = selected;
    next = Math.max(0, Math.min(list.length - 1, next));
    // Don't wrap into the next row via the right arrow.
    selected = next;
    highlight(true);
    return true;
  }
  function shortRevision(raw) {
    var full = raw === null || raw === undefined || raw === '' ? 'unknown' : String(raw);
    return /^[a-f0-9]{13,40}$/i.test(full) ? full.slice(0, 12) + '…' : full;
  }
  function renderDeployments(d) {
    window.GwayMonitorChannels.deployments.lastSnapshot = d;
    var node = el('deployment-list'); node.textContent = '';
    if (!d || !d.available) {
      items = []; selected = 0;
      value('deployment-summary', 'Deployment data unavailable');
      window.GwayMonitorChannels.deployments.footerText = 'Deployments unavailable';
      if (!el('deployments').hidden) value('channel-count', 'Deployments unavailable');
      return;
    }
    items = d.components || [];
    var countText = items.length + ' deployments · ' + (d.node || 'gway-001');
    window.GwayMonitorChannels.deployments.footerText = countText;
    if (!el('deployments').hidden) value('channel-count', countText);
    value('deployment-summary', items.length + ' configured components on ' + (d.node || 'gway-001'));
    if (!items.length) { node.textContent = 'No configured components reported'; selected = 0; return; }
    items.forEach(function (item) {
      var card = document.createElement('article');
      card.className = 'pr-card deployment-card';
      var name = document.createElement('h2');
      name.className = 'deployment-name';
      name.textContent = item.repository || item.name || 'Unknown component';
      var revision = item.revision === null || item.revision === undefined || item.revision === '' ? 'unknown' : String(item.revision);
      var details = document.createElement('div');
      details.className = 'deployment-revision';
      var caption = document.createElement('span'); caption.textContent = 'Revision:';
      var sha = document.createElement('code');
      sha.className = 'deployment-sha';
      sha.textContent = shortRevision(revision);
      sha.setAttribute('title', revision);
      sha.setAttribute('aria-label', 'Full revision: ' + revision);
      sha.setAttribute('data-full-revision', revision);
      details.appendChild(caption); details.appendChild(sha);
      var full = document.createElement('p');
      full.className = 'deployment-full-revision';
      full.textContent = 'Full revision: ' + revision;
      var parsed = item.deployed_at ? new Date(item.deployed_at) : null;
      var dateText = parsed && !isNaN(parsed.getTime()) ? parsed.toLocaleString() : 'Date unavailable';
      var date = document.createElement('p');
      date.className = 'deployment-date';
      date.textContent = 'Deployed: ' + dateText;
      var indicators = document.createElement('div');
      indicators.className = 'tv-chip-row deployment-indicators';
      indicators.appendChild(status.chip('Install', item.installation || 'unknown', status.signal('installation', item.installation)));
      indicators.appendChild(status.chip('Health', item.health || 'unknown', status.signal('health', item.health)));
      var overall = status.deployment(item).level;
      var retryLabel = active[item.name] ? 'Running' : errors[item.name] ? 'Failed' : overall === 'failed' ? 'Available (OK)' : 'Not needed';
      indicators.appendChild(status.chip('Retry', retryLabel, active[item.name] ? 'pending' : errors[item.name] ? 'failed' : overall === 'failed' ? 'pending' : 'idle'));
      card.appendChild(name); card.appendChild(details); card.appendChild(full); card.appendChild(date); card.appendChild(indicators);
      if (item.error || errors[item.name]) {
        var errorText = document.createElement('p');
        errorText.className = 'deployment-error';
        errorText.textContent = (item.error ? 'Evidence: ' + item.error : '') +
          (errors[item.name] ? (item.error ? ' · ' : '') + 'Retry: ' + errors[item.name] : '');
        card.appendChild(errorText);
      }
      node.appendChild(card);
    });
    highlight(false);
  }
  window.GwayMonitorChannels = window.GwayMonitorChannels || {};
  window.GwayMonitorChannels.deployments = {
    id:'deployments', order:3, title:'Deployments', snapshotKey:'deployments',
    render:renderDeployments, mount:function () { highlight(false); },
    unmount:function () {}, onKey:onKey, setRetry:setRetry, retryState:retryState
  };
}());
