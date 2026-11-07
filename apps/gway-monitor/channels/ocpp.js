(function () {
  'use strict';
  var fmt = window.GwayMonitorFormat;
  var el = fmt.el, value = fmt.value, number = fmt.number, temperature = fmt.temperature;
  var duration = fmt.duration, bytes = fmt.bytes, address = fmt.address;
  function renderTransaction(tx, label) {
    value('tx-title', label);
    var node = el('tx-content');
    node.textContent = '';
    if (!tx) { node.textContent = 'No recorded transaction'; return; }
    [['Charger', tx.charger_id], ['Connector', tx.connector_id], ['State', tx.state],
      ['Started', tx.started_at], ['Stopped', tx.stopped_at],
      ['Energy', typeof tx.energy_wh === 'number' ? number(tx.energy_wh / 1000, ' kWh') : null]]
      .forEach(function (entry) {
        var item = document.createElement('div'), title = document.createElement('span'), data = document.createElement('strong');
        item.className = 'tx-row'; title.textContent = entry[0]; data.textContent = entry[1] == null ? '—' : String(entry[1]);
        item.appendChild(title); item.appendChild(data); node.appendChild(item);
      });
  }
  function renderOcpp(o) {
    if (!o || o.available !== true) {
      value('server', 'Unavailable'); value('storage', 'CSMS status unavailable');
      value('chargers', '—'); value('tx-title', 'Current / last transaction');
      value('tx-content', 'Transaction data unavailable'); return;
    }
    value('server', o.server && typeof o.server.state === 'string' ? o.server.state : 'Unknown');
    value('storage', o.storage && typeof o.storage.database === 'string' ? 'Database: ' + o.storage.database + ' · Transactions: ' + (o.storage.transactions || 'unknown') : 'Storage unavailable');
    value('chargers', String(o.connected_count || 0) + ' / ' + String(o.charger_count || 0));
    if (!o.active_query_ok || !o.last_query_ok) {
      value('tx-content', 'Transaction query unavailable');
      value('tx-title', 'Current / last transaction');
    } else if (o.current) renderTransaction(o.current, 'Current transaction (recorded)');
    else renderTransaction(o.last, 'Last transaction (recorded)');
  }
  window.GwayMonitorChannels = window.GwayMonitorChannels || {};
  window.GwayMonitorChannels.ocpp = {id:'ocpp', title:'OCPP', snapshotKey:'ocpp', render:renderOcpp, mount:function () {}, unmount:function () {}};
}());
