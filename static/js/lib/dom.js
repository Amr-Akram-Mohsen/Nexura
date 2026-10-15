/**
 * Nexura — Shared DOM Utility (lib/dom.js)
 * Provides centralized HTML escaping, body scroll locking for modals/overlays,
 * and semantic visibility helpers.
 */
'use strict';

(function () {
  window.Nexura = window.Nexura || {};

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function lockScroll() {
    document.body.classList.add('is-scroll-locked');
  }

  function unlockScroll() {
    document.body.classList.remove('is-scroll-locked');
  }

  function show(el) {
    if (!el) return;
    el.removeAttribute('hidden');
    if (el.style.display === 'none') {
      el.style.display = '';
    }
  }

  function hide(el) {
    if (!el) return;
    el.setAttribute('hidden', '');
  }

  window.Nexura.dom = {
    escapeHtml,
    lockScroll,
    unlockScroll,
    show,
    hide,
  };
})();
