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
  window.GwayMonitorStatus = {github:github, deployment:deployment, badge:badge};
}());
