/* Static channel registry. Compatible with webOS Chromium 94. */
(function () {
  'use strict';
  function create(definitions, lookup) {
    if (!Array.isArray(definitions) || !definitions.length) throw new Error('No monitor channels');
    var seen = Object.create(null);
    var items = definitions.map(function (item) {
      if (!item || typeof item.id !== 'string' || !/^[a-z][a-z0-9-]*$/.test(item.id) ||
          seen[item.id] || typeof item.title !== 'string' || !item.title ||
          typeof item.render !== 'function' ||
          (item.snapshotKey !== undefined && (typeof item.snapshotKey !== 'string' || !/^[a-z][a-z0-9-]*$/.test(item.snapshotKey))) ||
          (item.mount !== undefined && typeof item.mount !== 'function') ||
          (item.unmount !== undefined && typeof item.unmount !== 'function') ||
          (item.onKey !== undefined && typeof item.onKey !== 'function') ||
          !lookup(item.id) || !lookup('tab-' + item.id)) {
        throw new Error('Invalid or duplicate monitor channel');
      }
      seen[item.id] = true;
      return item;
    });
    return {
      items: items,
      at: function (index) { return items[(index % items.length + items.length) % items.length]; },
      index: function (index) { return (index % items.length + items.length) % items.length; },
      render: function (snapshot) {
        items.forEach(function (item) { item.render(snapshot[item.snapshotKey || item.id]); });
      }
    };
  }
  window.GwayChannelRegistry = {create: create};
}());
