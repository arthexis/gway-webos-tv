(function () {
  'use strict';
  var fmt = window.GwayMonitorFormat;
  var el = fmt.el, value = fmt.value, number = fmt.number, temperature = fmt.temperature;
  var duration = fmt.duration, bytes = fmt.bytes, address = fmt.address;
  function renderHardware(h) {
    if (!h || h.available !== true) {
      ['ambient', 'soc', 'model', 'uptime', 'memory', 'disk', 'disk-free', 'eth0', 'wlan0', 'wlan1'].forEach(function (id) { value(id, 'Unavailable'); });
      return;
    }
    value('ambient', temperature(h.ambient_c));
    value('soc', temperature(h.soc_c));
    value('model', h.model);
    value('uptime', duration(h.uptime_seconds));
    var memory = h.memory || {}, disk = h.disk || {};
    value('memory', typeof memory.used_percent === 'number' ? number(memory.used_percent, '% used') : '—');
    value('disk', typeof disk.used_percent === 'number' ? number(disk.used_percent, '% used') : '—');
    value('disk-free', 'Free: ' + bytes(disk.free_bytes));
    var ips = h.interfaces || {};
    ['eth0', 'wlan0', 'wlan1'].forEach(function (id) { value(id, address(ips[id])); });
  }
  window.GwayMonitorChannels = window.GwayMonitorChannels || {};
  window.GwayMonitorChannels.hardware = {id:'hardware', order:0, title:'Hardware', snapshotKey:'hardware', render:renderHardware, mount:function () {}, unmount:function () {}};
}());
