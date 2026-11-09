(function () {
  'use strict';
  // Reports only DOM nodes already rendered by the TV. Never derives badges from snapshots.
  var SHA = /^[0-9a-f]{40}$/;
  var NONCE = /^[0-9a-f]{32}$/;
  function readDeployment(repository) {
    if (typeof repository !== 'string' || repository.length > 128) return null;
    var root = document.getElementById('deployments');
    if (!root || root.hidden) return null;
    var cards = root.querySelectorAll('#deployment-list > article');
    for (var i = 0; i < cards.length; i++) {
      var heading = cards[i].querySelector('h2');
      if (!heading || heading.textContent !== repository) continue;
      var badge = cards[i].querySelector('.status-badge');
      var label = badge && badge.querySelector('.status-label');
      if (!badge || !label) return null;
      return {repository: repository, badge: label.textContent,
        aria_label: badge.getAttribute('aria-label')};
    }
    return null;
  }
  function evidence(request, identity, now) {
    if (!request || request.type !== 'monitor.diagnostic.request' ||
        !NONCE.test(request.nonce || '') ||
        !Number.isFinite(request.expires_at) ||
        request.expires_at < now || request.expires_at > now + 10000 ||
        request.repository !== 'arthexis/gway-agent-ops' ||
        !identity || !SHA.test(identity.git_sha || '')) return null;
    var card = readDeployment(request.repository);
    return {type: 'monitor.diagnostic.result', nonce: request.nonce,
      build_id: identity.build_id, git_sha: identity.git_sha,
      channel: 'deployments', visible: !document.getElementById('deployments').hidden,
      card: card, observed_at: new Date(now).toISOString()};
  }
  window.GwayMonitorDiagnostic = {readDeployment: readDeployment, evidence: evidence};
}());
