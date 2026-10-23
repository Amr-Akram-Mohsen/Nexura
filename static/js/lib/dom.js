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

  let scrollLockCount = 0;

  function lockScroll() {
    scrollLockCount++;
    document.body.classList.add('is-scroll-locked');
  }

  function unlockScroll() {
    scrollLockCount = Math.max(0, scrollLockCount - 1);
    if (scrollLockCount === 0) {
      document.body.classList.remove('is-scroll-locked');
    }
  }

  function show(el) {
    if (!el) return;
    el.removeAttribute('hidden');
    el.classList.remove('is-hidden');
  }

  function hide(el) {
    if (!el) return;
    el.setAttribute('hidden', '');
    el.classList.add('is-hidden');
  }

  function toggle(el, condition) {
    if (!el) return;
    const shouldShow = typeof condition === 'boolean' ? condition : el.hasAttribute('hidden');
    if (shouldShow) {
      show(el);
    } else {
      hide(el);
    }
  }

  window.Nexura.dom = {
    escapeHtml,
    lockScroll,
    unlockScroll,
    show,
    hide,
    toggle,
  };
})();
