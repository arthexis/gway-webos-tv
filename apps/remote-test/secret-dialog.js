/* Remote-operated six-digit dialog; does not persist or log the entered code. */
(function (global) {
  'use strict';
  global.GwaySecretDialog = {
    create: function (options) {
      var overlay = document.createElement('div');
      overlay.className = 'secret-overlay';
      overlay.hidden = true;
      overlay.innerHTML = '<section class="secret-dialog" role="dialog" aria-modal="true" aria-labelledby="secret-title"><h2 id="secret-title">Connect to GWAY</h2><p>Generate a six-digit code on GWAY, then enter it with the remote.</p><div class="secret-digits" aria-live="polite"></div><p class="secret-hint">Numbers: enter code &nbsp; · &nbsp; Back: erase &nbsp; · &nbsp; OK: connect</p></section>';
      document.body.appendChild(overlay);
      var digits = '', active = false;
      var display = overlay.querySelector('.secret-digits');
      function render() { display.textContent = '\u25cf'.repeat(digits.length) + '\u25cb'.repeat(6 - digits.length); }
      function close() { active = false; digits = ''; overlay.hidden = true; render(); }
      document.addEventListener('keydown', function (event) {
        if (!active) return;
        var key = event.keyCode || event.which || 0;
        var digit = key >= 48 && key <= 57 ? String(key - 48) : key >= 96 && key <= 105 ? String(key - 96) : /^[0-9]$/.test(event.key || '') ? event.key : '';
        event.preventDefault();
        event.stopImmediatePropagation();
        if (digit && digits.length < 6) digits += digit;
        else if (key === 8 || key === 461) {
          if (digits.length) digits = digits.slice(0, -1);
          else { close(); if (options.onCancel) options.onCancel(); return; }
        } else if (key === 27) { close(); if (options.onCancel) options.onCancel(); return; }
        else if (key === 13 && digits.length === 6) {
          var result = digits; close(); options.onSubmit(result); return;
        }
        render();
      }, true);
      return {open: function () { digits = ''; active = true; overlay.hidden = false; render(); }, close: close, isOpen: function () { return active; }};
    }
  };
}(window));
