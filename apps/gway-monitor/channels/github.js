(function () {
  'use strict';
  var el = window.GwayMonitorFormat.el, value = window.GwayMonitorFormat.value;
  var status = window.GwayMonitorStatus, selected = 0;
  function cards() { return el('pr-list').children; }
  function highlight(scroll) {
    var list = cards();
    if (!list.length) { selected = 0; return; }
    selected = Math.max(0, Math.min(selected, list.length - 1));
    Array.prototype.forEach.call(list, function (card, i) {
      card.classList.toggle('selected-card', i === selected);
      if (typeof card.setAttribute === 'function') card.setAttribute('aria-current', i === selected ? 'true' : 'false');
    });
    if (scroll) {
      var viewport = el('github'), cardRect = list[selected].getBoundingClientRect(), viewRect = viewport.getBoundingClientRect();
      if (cardRect.bottom > viewRect.bottom) viewport.scrollTop += cardRect.bottom - viewRect.bottom;
      else if (cardRect.top < viewRect.top) viewport.scrollTop -= viewRect.top - cardRect.top;
    }
  }
  function onKey(code) {
    if (code !== 38 && code !== 40) return false;
    var list = cards();
    if (list.length) {
      selected = Math.max(0, Math.min(list.length - 1, selected + (code === 38 ? -1 : 1)));
      highlight(true);
    }
    return true;
  }
  function renderGithub(g) {
    var node = el('pr-list'); node.textContent = '';
    if (!g) {
      value('pr-summary', 'Unavailable');
      window.GwayMonitorChannels.github.footerText = 'PRs unavailable';
      value('channel-count', 'PRs unavailable');
      selected = 0; return;
    }
    var prs = g.pull_requests || [];
    var countText = prs.length + ' open PRs · ' + (g.repositories || []).length + ' repos';
    window.GwayMonitorChannels.github.footerText = countText;
    if (!el('github').hidden) value('channel-count', countText);
    value('pr-summary', countText + (g.errors && g.errors.length ? ' · Errors: ' + g.errors.join(', ') : ''));
    if (!prs.length) {
      node.textContent = g.errors && g.errors.length ? 'GitHub data unavailable' : 'No open PRs';
      selected = 0; return;
    }
    prs.forEach(function (pr) {
      var card = document.createElement('article');
      card.className = 'pr-card github-card';
      var heading = document.createElement('h2');
      heading.className = 'github-repo';
      heading.textContent = (pr.repo || 'Unknown repository') + ' #' + (pr.number || '?');
      var title = document.createElement('p');
      title.className = 'github-title';
      title.textContent = pr.title || 'Untitled pull request';
      var indicators = document.createElement('div');
      indicators.className = 'tv-chip-row';
      indicators.appendChild(status.chip('State', pr.draft ? 'Draft' : 'Open', pr.draft ? 'draft' : 'passed'));
      indicators.appendChild(status.chip('CI', pr.ci || 'unknown', status.signal('ci', pr.ci)));
      indicators.appendChild(status.chip('Merge', pr.merge || 'unknown', status.signal('merge', pr.merge)));
      card.appendChild(heading);
      card.appendChild(title);
      card.appendChild(indicators);
      node.appendChild(card);
    });
    highlight(false);
  }
  window.GwayMonitorChannels = window.GwayMonitorChannels || {};
  window.GwayMonitorChannels.github = {
    id:'github', order:2, title:'GitHub PRs', snapshotKey:'github',
    render:renderGithub, mount:function () { highlight(false); },
    unmount:function () {}, onKey:onKey
  };
}());
