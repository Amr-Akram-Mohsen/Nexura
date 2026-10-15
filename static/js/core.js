/**
 * Nexura — Core Application Bootstrap (core.js)
 * Manages site-wide notifications (Toast), theme switching, responsive navigation,
 * hero carousel, progressive grid reveal, alert dismissal, and flash message dispatch.
 */
'use strict';

(function () {
  window.Nexura = window.Nexura || {};

  function getCsrfToken() {
    if (window.Nexura.http && typeof window.Nexura.http.getCsrfToken === 'function') {
      return window.Nexura.http.getCsrfToken();
    }
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
  }

  /* ── Toast Notification System ───────────────────────────────────────────── */
  const Toast = {
    container: null,

    _getContainer() {
      if (!this.container) {
        this.container = document.createElement('div');
        this.container.className = 'toast-container';
        this.container.setAttribute('aria-live', 'polite');
        this.container.setAttribute('aria-atomic', 'false');
        document.body.appendChild(this.container);
      }
      return this.container;
    },

    show(message, type = 'info', duration = null, title = null) {
      const c = this._getContainer();
      const toast = document.createElement('div');
      toast.className = `toast toast--${type}`;
      toast.setAttribute('role', 'alert');

      const icons = {
        success: `<svg class="toast__icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
        error: `<svg class="toast__icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
        warning: `<svg class="toast__icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
        info: `<svg class="toast__icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
      };

      const effectiveDuration = duration || (type === 'error' || type === 'warning' ? 4000 : 2500);

      toast.innerHTML = `
        ${icons[type] || icons.info}
        <span class="toast__message">${message}</span>
        <button type="button" class="toast__close" aria-label="Dismiss notification">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      `;
      c.appendChild(toast);

      let timer = null;
      let remaining = effectiveDuration;
      let startTime = Date.now();

      const dismiss = () => {
        toast.classList.add('toast--exit');
        toast.addEventListener('animationend', () => toast.remove(), { once: true });
      };

      const startTimer = () => {
        startTime = Date.now();
        timer = setTimeout(dismiss, remaining);
      };

      const pauseTimer = () => {
        clearTimeout(timer);
        remaining -= Date.now() - startTime;
      };

      toast.addEventListener('mouseenter', pauseTimer);
      toast.addEventListener('mouseleave', () => {
        if (remaining > 0) startTimer();
        else dismiss();
      });

      const closeBtn = toast.querySelector('.toast__close');
      if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          clearTimeout(timer);
          dismiss();
        });
      }

      startTimer();
    },
  };

  window.Nexura.toast = Toast.show.bind(Toast);
  window.Toast = Toast;

  /* ── Theme Manager ───────────────────────────────────────────────────────── */
  const ThemeManager = {
    STORAGE_KEY: 'nx-theme',

    init() {
      const saved = localStorage.getItem(this.STORAGE_KEY);
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      const theme = saved || (prefersDark ? 'dark' : 'light');
      this._apply(theme);
    },

    toggle() {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      this._apply(next);
      localStorage.setItem(this.STORAGE_KEY, next);
    },

    _apply(theme) {
      document.documentElement.setAttribute('data-theme', theme);
      const btn = document.querySelector('[data-action="toggle-theme"]');
      if (btn) {
        btn.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
        btn.innerHTML =
          theme === 'dark'
            ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`
            : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
      }
    },
  };

  /* ── Hero Carousel ───────────────────────────────────────────────────────── */
  const HeroCarousel = {
    el: null,
    slides: [],
    dots: [],
    current: 0,
    timer: null,
    INTERVAL: 5500,

    init(el) {
      if (!el) return;
      this.el = el;
      this.slides = [...el.querySelectorAll('.hero-slide')];
      this.dots = [...el.querySelectorAll('.hero__dot')];
      if (this.slides.length < 2) return;
      this.goto(0);
      this.start();
      this.el.addEventListener('mouseenter', () => this.stop());
      this.el.addEventListener('mouseleave', () => this.start());
    },

    goto(idx) {
      this.slides.forEach((s, i) => s.classList.toggle('active', i === idx));
      this.dots.forEach((d, i) => d.classList.toggle('active', i === idx));
      this.current = idx;
    },

    next() {
      this.goto((this.current + 1) % this.slides.length);
    },

    start() {
      this.stop();
      this.timer = setInterval(() => this.next(), this.INTERVAL);
    },

    stop() {
      clearInterval(this.timer);
    },
  };

  /* ── Progressive Reveal ─────────────────────────────────────────────────── */
  const ProgressiveReveal = {
    init(containerSelector = '.grid-cards[data-reveal]', btnSelector = '[data-reveal-trigger]') {
      const containers = document.querySelectorAll(containerSelector);
      containers.forEach((container) => {
        const parentSection = container.closest('section') || container.parentElement;
        const btn = parentSection ? parentSection.querySelector(btnSelector) : null;
        if (!btn) return;

        const hidden = [...container.querySelectorAll('.reveal-item:nth-child(n+7)')];
        if (hidden.length === 0) {
          btn.classList.add('hidden');
          btn.style.display = 'none';
          return;
        }

        btn.addEventListener('click', () => {
          const batch = hidden.splice(0, 6);
          batch.forEach((item, i) => {
            item.style.setProperty('--reveal-idx', i);
            item.classList.add('revealed');
          });

          if (hidden.length === 0) {
            btn.classList.add('hidden');
            btn.style.display = 'none';
          }
        });
      });
    },
  };

  /* ── Mobile Navigation Drawer ───────────────────────────────────────────── */
  function initMobileNav() {
    const burger = document.querySelector('[data-action="toggle-nav"]');
    const nav = document.querySelector('.navbar__nav');
    if (!burger || !nav) return;

    burger.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      burger.setAttribute('aria-expanded', open);
    });

    document.addEventListener('click', (e) => {
      if (!burger.contains(e.target) && !nav.contains(e.target)) {
        nav.classList.remove('open');
        burger.setAttribute('aria-expanded', false);
      }
    });
  }

  /* ── Delegated Core Shell Click Handlers ─────────────────────────────────── */
  document.addEventListener('click', (e) => {
    const target = e.target;

    if (target.closest('[data-action="toggle-theme"]')) {
      ThemeManager.toggle();
      return;
    }

    const dot = target.closest('.hero__dot');
    if (dot) {
      const idx = parseInt(dot.dataset.idx, 10);
      if (!isNaN(idx)) HeroCarousel.goto(idx);
      return;
    }

    if (target.closest('[data-action="toggle-nav"]')) {
      return;
    }
  });

  /* ── Password Visibility Toggles ────────────────────────────────────────── */
  function initPasswordToggles() {
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.auth-field__toggle-btn');
      if (!btn) return;

      e.preventDefault();
      const wrapper = btn.closest('.auth-field__input-wrapper');
      if (!wrapper) return;

      const input = wrapper.querySelector('input');
      if (!input) return;

      const isCurrentlyPassword = input.type === 'password';
      input.type = isCurrentlyPassword ? 'text' : 'password';
      btn.setAttribute('aria-label', isCurrentlyPassword ? 'Hide password' : 'Show password');
      btn.setAttribute('aria-pressed', isCurrentlyPassword ? 'true' : 'false');
    });
  }

  /* ── Alert Dismissals ────────────────────────────────────────────────────── */
  function initAlertDismissals() {
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.alert__close, [data-action="dismiss-alert"]');
      if (!btn) return;

      e.preventDefault();
      const alert = btn.closest('.alert');
      if (!alert) return;

      alert.classList.add('alert--collapsing');
      alert.addEventListener(
        'transitionend',
        () => {
          alert.remove();
        },
        { once: true }
      );

      // Fallback in case transitionend does not fire
      setTimeout(() => {
        if (alert.parentNode) {
          alert.remove();
        }
      }, 350);
    });
  }

  /* ── Global Image Error Fallback Handler (capturing phase) ───────────────── */
  window.addEventListener(
    'error',
    (e) => {
      const target = e.target;
      if (target && target.tagName === 'IMG') {
        if (target.classList.contains('search-result-row__thumb')) {
          if (target.parentElement) {
            target.parentElement.classList.add('no-thumb');
          }
        } else {
          target.hidden = true;
        }
      }
    },
    true
  );

  /* ── Flashed Messages Dispatcher ─────────────────────────────────────────── */
  function initFlashedMessages() {
    const el = document.getElementById('flashed-messages-data');
    if (!el) return;

    try {
      const raw = el.getAttribute('data-messages');
      if (!raw) return;
      const messages = JSON.parse(raw);
      messages.forEach(([category, message], index) => {
        setTimeout(() => {
          const type =
            category === 'error' || category === 'danger'
              ? 'error'
              : category === 'success'
                ? 'success'
                : category === 'warning'
                  ? 'warning'
                  : 'info';
          Toast.show(message, type);
        }, index * 250);
      });
    } catch (err) {
      console.error('Failed to parse flashed messages:', err);
    }
  }

  /* ── DOM Ready Initializer ───────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', () => {
    ThemeManager.init();
    HeroCarousel.init(document.querySelector('.hero-carousel'));
    ProgressiveReveal.init('.grid-cards[data-reveal]', '[data-reveal-trigger]');
    initMobileNav();
    initPasswordToggles();
    initAlertDismissals();
    initFlashedMessages();
  });
})();
