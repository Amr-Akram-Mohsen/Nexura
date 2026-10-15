/**
 * Early theme initialization to prevent Flash of Unstyled Content (FOUC).
 * Runs synchronously in <head> before DOM content is rendered.
 */
(function () {
  'use strict';
  try {
    const STORAGE_KEY = 'nx-theme';
    const saved = localStorage.getItem(STORAGE_KEY);
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = saved || (prefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) {
    // Fallback gracefully in case of localStorage access restrictions (e.g. private browsing)
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
