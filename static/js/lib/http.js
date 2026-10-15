/**
 * Nexura — Shared HTTP & CSRF Utility (lib/http.js)
 * Centralizes CSRF token extraction, request headers, JSON/form payload handling,
 * and standardized error parsing across public and admin interfaces.
 */
'use strict';

(function () {
  window.Nexura = window.Nexura || {};

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    const input = document.querySelector('input[name="csrf_token"]');
    return input ? input.value : '';
  }

  async function request(url, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const headers = Object.assign({}, options.headers || {});

    headers['X-Requested-With'] = 'XMLHttpRequest';

    let body = options.body;
    if (method !== 'GET' && method !== 'HEAD') {
      const csrf = getCsrfToken();
      if (csrf && !headers['X-CSRFToken']) {
        headers['X-CSRFToken'] = csrf;
      }

      if (
        body &&
        typeof body === 'object' &&
        !(body instanceof FormData) &&
        !(body instanceof URLSearchParams)
      ) {
        if (!headers['Content-Type']) {
          headers['Content-Type'] = 'application/json';
        }
        body = JSON.stringify(body);
      }
    }

    const res = await fetch(url, {
      ...options,
      method,
      headers,
      body,
    });

    if (!res.ok) {
      let errData = {};
      try {
        errData = await res.json();
      } catch (_) {
        errData = { message: res.statusText };
      }
      const message =
        errData.message || errData.error || `Request failed with status ${res.status}`;
      const err = new Error(message);
      err.status = res.status;
      err.data = errData;
      throw err;
    }

    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      return res.json().catch(() => ({}));
    }
    return res.text();
  }

  window.Nexura.http = {
    get: (url, opts) => request(url, { ...opts, method: 'GET' }),
    post: (url, body, opts) => request(url, { ...opts, method: 'POST', body }),
    request,
    getCsrfToken,
  };
})();
