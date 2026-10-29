/* Glue between the page and the Android shell (MainActivity exposes window.ConNuocAndroid). */
(function () {
  'use strict';
  var A = window.ConNuocAndroid;
  if (!A) return;

  // Clipboard: copy through the native ClipboardManager, which works without the
  // permission prompts the WebView clipboard API may need.
  var writeText = function (text) {
    try { A.copyText(String(text)); return Promise.resolve(); }
    catch (e) { return Promise.reject(e); }
  };
  try {
    if (navigator.clipboard) navigator.clipboard.writeText = writeText;
    else Object.defineProperty(navigator, 'clipboard', { value: { writeText: writeText } });
  } catch (e) { /* keep the page's own fallback */ }

  // System bars follow the page's light/dark theme.
  var root = document.documentElement, last = '';
  function syncBars() {
    var bg = getComputedStyle(root).getPropertyValue('--bg').trim();
    if (!/^#[0-9a-f]{6}$/i.test(bg) || bg === last) return;
    last = bg;
    try { A.setBackground(bg); } catch (e) { /* ignore */ }
  }
  new MutationObserver(syncBars).observe(root, { attributes: true, attributeFilter: ['data-theme'] });
  try { matchMedia('(prefers-color-scheme: dark)').addEventListener('change', syncBars); } catch (e) { /* old WebView */ }
  syncBars();
})();
