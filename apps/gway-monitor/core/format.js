(function () {
  'use strict';
  function el(id) { return document.getElementById(id); }
  function value(id, text) { el(id).textContent = text === null || text === undefined || text === '' ? '—' : String(text); }
  function number(n, suffix) { return typeof n === 'number' && isFinite(n) ? n.toFixed(1) + (suffix || '') : '—'; }
  function temperature(n) { return number(n, ' °C'); }
  function duration(seconds) {
    if (typeof seconds !== 'number' || seconds < 0) return '—';
    return Math.floor(seconds / 86400) + 'd ' + Math.floor(seconds % 86400 / 3600) + 'h';
  }
  function bytes(n) { return typeof n === 'number' && n >= 0 ? (n / 1073741824).toFixed(1) + ' GiB' : '—'; }
  function address(info) {
    if (!info || info.present !== true) return 'Not installed';
    if (info.up !== true) return 'Down';
    if (!Array.isArray(info.ipv4) || !info.ipv4.length) return 'No IPv4 address';
    return info.ipv4.join(', ');
  }
  window.GwayMonitorFormat = {el:el,value:value,number:number,temperature:temperature,duration:duration,bytes:bytes,address:address};
}());
