(function () {
  'use strict';
  var fmt = window.GwayMonitorFormat;
  var el = fmt.el, value = fmt.value, number = fmt.number, temperature = fmt.temperature;
  var duration = fmt.duration, bytes = fmt.bytes, address = fmt.address;
  var selected = 0;
  function cards() { return el('pr-list').children; }
  function highlight(scroll) {
    var list = cards();
    if (!list.length) return;
    selected = Math.max(0, Math.min(selected, list.length - 1));
    Array.prototype.forEach.call(list, function (card, i) { card.classList.toggle('selected-card', i === selected); });
    if (scroll) {
      var viewport = el('github');
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
  function renderGithub(g) {
    var node = el('pr-list'); node.textContent = '';
    if (!g) { value('pr-summary', 'Unavailable'); return; }
    var prs = g.pull_requests || [];
    value('pr-summary', prs.length + ' open PRs · ' + (g.repositories || []).length + ' repos' + (g.errors && g.errors.length ? ' · Errors: ' + g.errors.join(', ') : ''));
    if (!prs.length) { node.textContent = g.errors && g.errors.length ? 'GitHub data unavailable' : 'No open PRs'; return; }
    prs.forEach(function (pr) {
      var card = document.createElement('article'); card.className = 'pr-card';
      var heading = document.createElement('h2'); heading.textContent = pr.repo + ' #' + pr.number;
      var title = document.createElement('p'); title.textContent = pr.title;
      var status = document.createElement('p'); status.className = 'muted';
      status.textContent = (pr.draft ? 'Draft' : 'Open') + ' · CI: ' + pr.ci + ' · Merge: ' + (pr.merge || 'unknown');
      var text = document.createElement('div'); text.className = 'status-copy';
      text.appendChild(heading); text.appendChild(title); text.appendChild(status);
      card.appendChild(text); card.appendChild(window.GwayMonitorStatus.badge(window.GwayMonitorStatus.github(pr))); node.appendChild(card);
    });
    highlight(false);
  }
  window.GwayMonitorChannels = window.GwayMonitorChannels || {};
  window.GwayMonitorChannels.github = {id:'github', order:2, title:'GitHub PRs', snapshotKey:'github', render:renderGithub, mount:function () { highlight(false);}, unmount:function () {}, onKey:onKey};
}());
