(function () {
  'use strict';
  function norm(value) { return typeof value === 'string' ? value.trim().toLowerCase().replace(/[ _-]+/g, '') : ''; }
  function result(level, label) { return {level:level, label:label}; }
  function github(pr) {
    if (!pr || typeof pr !== 'object') return result('unknown', 'Unknown');
    var ci = norm(pr.ci), merge = norm(pr.merge);
    if (ci === 'failed' || ['dirty','blocked','conflicting'].indexOf(merge) !== -1) return result('failed', 'Blocked');
    if (pr.draft === true) return result('draft', 'Draft');
    if (ci === 'pending') return result('pending', 'Running');
    if (ci === 'passed' && ['clean','hashooks','unstable'].indexOf(merge) !== -1) return result('passed', 'Ready');
    return result('unknown', 'Unknown');
  }
  function deployment(item) {
    if (!item || typeof item !== 'object') return result('unknown', 'Unknown');
    var install = norm(item.installation), health = norm(item.health);
    if (item.error || ['failed','error','failure'].indexOf(install) !== -1 ||
        ['failed','error','unhealthy','dead'].indexOf(health) !== -1) return result('failed', 'Failed');
    if (['installing','deploying','updating','pending','running'].indexOf(install) !== -1) return result('pending', 'Updating');
    if (['degraded','warning'].indexOf(health) !== -1) return result('degraded', 'Degraded');
    // Only show 'outdated' when the collector supplies explicit comparable revisions.
    if (item.outdated === true || (item.target_revision && item.revision && item.target_revision !== item.revision)) return result('outdated', 'Outdated');
    if (['installed','active','activated','success','succeeded','ok'].indexOf(install) !== -1 &&
        ['healthy','active','running','ok','success'].indexOf(health) !== -1) return result('passed', 'Healthy');
    if (install === 'activated' && health === 'notapplicable' &&
        item.runtime_required === false && item.verified_release === true) return result('passed', 'Installed');
    return result('unknown', 'Unknown');
  }
  var symbols = {passed:'✓',failed:'×',pending:'↻',draft:'✎',outdated:'↓',degraded:'!',unknown:'?'};
  function badge(state) {
    var node = document.createElement('div');
    node.className = 'status-badge status-' + state.level;
    node.setAttribute('role', 'img');
    node.setAttribute('aria-label', state.label);
    var symbol = document.createElement('span'); symbol.className = 'status-symbol'; symbol.textContent = symbols[state.level] || '?';
    var label = document.createElement('span'); label.className = 'status-label'; label.textContent = state.label;
    node.appendChild(symbol); node.appendChild(label);
    return node;
  }

  // Small independent indicators keep each state visible without conflating
  // Draft, CI and mergeability (or installation, health and retry).
  function chip(label, raw, level) {
    var allowed = {passed:1, failed:1, pending:1, draft:1, unknown:1, degraded:1, outdated:1};
    var tone = allowed[level] ? level : 'unknown';
    var shown = (raw === null || raw === undefined || String(raw).trim() === '') ? 'unknown' : String(raw);
    var node = document.createElement('span');
    node.className = 'tv-chip status-' + tone;
    node.setAttribute('role', 'img');
    node.setAttribute('aria-label', label + ': ' + shown);
    var mark = document.createElement('span');
    mark.className = 'tv-chip-icon';
    mark.setAttribute('aria-hidden', 'true');
    mark.textContent = symbols[tone] || '?';
    var detail = document.createElement('span');
    detail.className = 'tv-chip-text';
    detail.textContent = label + ': ' + shown;
    node.appendChild(mark);
    node.appendChild(detail);
    return node;
  }
  function signal(group, value) {
    var word = norm(value);
    if (group === 'ci') {
      if (['passed','success','succeeded'].indexOf(word) !== -1) return 'passed';
      if (['failed','failure','error'].indexOf(word) !== -1) return 'failed';
      if (['pending','running','queued','inprogress'].indexOf(word) !== -1) return 'pending';
    } else if (group === 'merge') {
      if (['clean','hashooks'].indexOf(word) !== -1) return 'passed';
      if (['blocked','dirty','conflicting'].indexOf(word) !== -1) return 'failed';
      if (['behind','pending'].indexOf(word) !== -1) return 'pending';
      if (word === 'unstable') return 'degraded';
    } else if (group === 'installation') {
      if (['activated','installed','active','success','succeeded','ok'].indexOf(word) !== -1) return 'passed';
      if (['failed','failure','error'].indexOf(word) !== -1) return 'failed';
      if (['installing','deploying','updating','pending','running'].indexOf(word) !== -1) return 'pending';
      if (word === 'staged') return 'degraded';
    } else if (group === 'health') {
      if (['healthy','active','running','ok','success'].indexOf(word) !== -1) return 'passed';
      if (['failed','error','unhealthy','dead'].indexOf(word) !== -1) return 'failed';
      if (['degraded','warning'].indexOf(word) !== -1) return 'degraded';
    }
    return 'unknown';
  }

  window.GwayMonitorStatus = {github:github, deployment:deployment, badge:badge, chip:chip, signal:signal};
}());
