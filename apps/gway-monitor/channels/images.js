(function () {
  'use strict';
  var groups = [], setIndex = 0, positions = {}, cache = {}, request = function () {}, animating = false, pendingDirection = '';
  var zoomed = false, panX = 0, panY = 0, zoomImage = '';
  function el(id) { return document.getElementById(id); }
  function key(group) { return group.length ? group[group.length - 1].id : ''; }
  function position(group) { var index = group.findIndex(function (item) { return item.id === positions[key(group)]; }); return index < 0 ? 0 : index; }
  function current() { var group = groups[setIndex]; return group && group[position(group)]; }
  function applyZoom() {
    var img = el('image-roll-current'), stage = img.parentElement;
    if (!zoomed || !stage) { img.style.transform = ''; img.classList.remove('zoomed'); return; }
    var maxX = Math.max(0, (img.clientWidth * 2 - stage.clientWidth) / 2);
    var maxY = Math.max(0, (img.clientHeight * 2 - stage.clientHeight) / 2);
    panX = Math.max(-maxX, Math.min(maxX, panX)); panY = Math.max(-maxY, Math.min(maxY, panY));
    img.className = 'zoomed';
    img.style.transform = 'translate(' + panX + 'px, ' + panY + 'px) scale(2)';
  }
  function resetZoom() { zoomed = false; panX = 0; panY = 0; zoomImage = ''; applyZoom(); }
  function draw(direction) {
    var img = el('image-roll-current'), empty = el('image-roll-empty'), item = current();
    empty.hidden = !!item;
    if (!item) { img.hidden = true; img.removeAttribute('src'); el('image-roll-position').textContent = ''; return; }
    if (zoomed && zoomImage !== item.id) resetZoom();
    var date = new Date(item.captured_at);
    el('image-roll-position').textContent = (isNaN(date.getTime()) ? '' : date.toLocaleString()) + '  ·  ' + item.filename + (zoomed ? '  ·  ZOOM' : '');
    if (cache[item.id]) {
      img.src = cache[item.id]; img.hidden = false; img.className = '';
      if (direction && !zoomed) { void img.offsetWidth; img.className = 'slide-from-' + direction; }
      if (zoomed) applyZoom();
    } else { img.hidden = true; pendingDirection = direction || ''; request(item.id); }
  }
  function update(value) {
    if (!Array.isArray(value)) return;
    var selected = groups[setIndex], selectedKey = selected && key(selected), previous = current();
    groups = value.filter(Array.isArray).map(function (group) {
      return group.filter(function (x) { return x && typeof x.id === 'string' && typeof x.filename === 'string' && typeof x.captured_at === 'string'; });
    }).filter(function (group) { return group.length; }).slice(0, 10);
    var found = groups.findIndex(function (group) { return key(group) === selectedKey; });
    setIndex = found < 0 ? 0 : found;
    if (previous && found >= 0) {
      var i = groups[setIndex].findIndex(function (item) { return item.id === previous.id; });
      positions[key(groups[setIndex])] = i < 0 ? groups[setIndex][0].id : previous.id;
    }
    draw(0);
  }
  function image(id, data) {
    if (typeof id !== 'string' || typeof data !== 'string' || data.indexOf('data:image/jpeg;base64,') !== 0) return;
    cache[id] = data;
    if (current() && current().id === id) { var direction = pendingDirection; pendingDirection = ''; draw(direction); }
  }
  function onKey(code) {
    if (code === 13) {
      if (!current() || !cache[current().id]) return true;
      if (zoomed) resetZoom();
      else { zoomed = true; zoomImage = current().id; panX = 0; panY = 0; }
      draw(0); return true;
    }
    if ([37, 38, 39, 40].indexOf(code) < 0) return false;
    if (zoomed) {
      var stage = el('image-roll-current').parentElement;
      var step = Math.max(40, Math.round(Math.min(stage.clientWidth, stage.clientHeight) * 0.18));
      if (code === 37) panX += step; if (code === 39) panX -= step;
      if (code === 38) panY += step; if (code === 40) panY -= step;
      applyZoom(); return true;
    }
    if (!groups.length || animating) return true;
    var direction = (code === 39 || code === 40) ? 1 : -1;
    if (code === 37 || code === 39) {
      var group = groups[setIndex], k = key(group), next = position(group) + direction;
      if (next < 0 || next >= group.length) return true;
      positions[k] = group[next].id;
    } else {
      var target = setIndex + direction;
      if (target < 0 || target >= groups.length) return true;
      setIndex = target;
    }
    var slide = code === 37 ? 'left' : code === 39 ? 'right' : code === 38 ? 'top' : 'bottom';
    animating = true; draw(slide);
    setTimeout(function () { animating = false; }, 300);
    return true;
  }
  window.GwayMonitorChannels = window.GwayMonitorChannels || {};
  window.GwayMonitorChannels.images = {id:'images', order:5, title:'Images', render:function () {}, update:update, image:image, onKey:onKey,
    setRequest:function (fn) { request = fn; }, mount:function () { draw(0); },
    unmount:function () { resetZoom(); groups = []; setIndex = 0; positions = {}; cache = {}; animating = false; pendingDirection = ''; }};
}());
