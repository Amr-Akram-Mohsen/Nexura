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

    _createIcon(type) {
      const svgNs = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(svgNs, 'svg');
      svg.setAttribute('class', 'toast__icon');
      svg.setAttribute('width', '14');
      svg.setAttribute('height', '14');
      svg.setAttribute('viewBox', '0 0 24 24');
      svg.setAttribute('fill', 'none');
      svg.setAttribute('stroke', 'currentColor');
      svg.setAttribute('stroke-width', '2.5');
      svg.setAttribute('stroke-linecap', 'round');
      svg.setAttribute('stroke-linejoin', 'round');
      svg.setAttribute('aria-hidden', 'true');

      if (type === 'success') {
        const poly = document.createElementNS(svgNs, 'polyline');
        poly.setAttribute('points', '20 6 9 17 4 12');
        svg.appendChild(poly);
      } else if (type === 'error') {
        const circle = document.createElementNS(svgNs, 'circle');
        circle.setAttribute('cx', '12');
        circle.setAttribute('cy', '12');
        circle.setAttribute('r', '10');
        const l1 = document.createElementNS(svgNs, 'line');
        l1.setAttribute('x1', '15');
        l1.setAttribute('y1', '9');
        l1.setAttribute('x2', '9');
        l1.setAttribute('y2', '15');
        const l2 = document.createElementNS(svgNs, 'line');
        l2.setAttribute('x1', '9');
        l2.setAttribute('y1', '9');
        l2.setAttribute('x2', '15');
        l2.setAttribute('y2', '15');
        svg.append(circle, l1, l2);
      } else if (type === 'warning') {
        const path = document.createElementNS(svgNs, 'path');
        path.setAttribute(
          'd',
          'M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z'
        );
        const l1 = document.createElementNS(svgNs, 'line');
        l1.setAttribute('x1', '12');
        l1.setAttribute('y1', '9');
        l1.setAttribute('x2', '12');
        l1.setAttribute('y2', '13');
        const l2 = document.createElementNS(svgNs, 'line');
        l2.setAttribute('x1', '12');
        l2.setAttribute('y1', '17');
        l2.setAttribute('x2', '12.01');
        l2.setAttribute('y2', '17');
        svg.append(path, l1, l2);
      } else {
        const circle = document.createElementNS(svgNs, 'circle');
        circle.setAttribute('cx', '12');
        circle.setAttribute('cy', '12');
        circle.setAttribute('r', '10');
        const l1 = document.createElementNS(svgNs, 'line');
        l1.setAttribute('x1', '12');
        l1.setAttribute('y1', '8');
        l1.setAttribute('x2', '12');
        l1.setAttribute('y2', '12');
        const l2 = document.createElementNS(svgNs, 'line');
        l2.setAttribute('x1', '12');
        l2.setAttribute('y1', '16');
        l2.setAttribute('x2', '12.01');
        l2.setAttribute('y2', '16');
        svg.append(circle, l1, l2);
      }
      return svg;
    },

    _createCloseBtn() {
      const svgNs = 'http://www.w3.org/2000/svg';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'toast__close';
      btn.setAttribute('aria-label', 'Dismiss notification');
      const svg = document.createElementNS(svgNs, 'svg');
      svg.setAttribute('width', '12');
      svg.setAttribute('height', '12');
      svg.setAttribute('viewBox', '0 0 24 24');
      svg.setAttribute('fill', 'none');
      svg.setAttribute('stroke', 'currentColor');
      svg.setAttribute('stroke-width', '2.5');
      svg.setAttribute('stroke-linecap', 'round');
      svg.setAttribute('stroke-linejoin', 'round');
      svg.setAttribute('aria-hidden', 'true');
      const l1 = document.createElementNS(svgNs, 'line');
      l1.setAttribute('x1', '18');
      l1.setAttribute('y1', '6');
      l1.setAttribute('x2', '6');
      l1.setAttribute('y2', '18');
      const l2 = document.createElementNS(svgNs, 'line');
      l2.setAttribute('x1', '6');
      l2.setAttribute('y1', '6');
      l2.setAttribute('x2', '18');
      l2.setAttribute('y2', '18');
      svg.append(l1, l2);
      btn.appendChild(svg);
      return btn;
    },

    show(message, type = 'info', duration = null, title = null) {
      const c = this._getContainer();
      const toast = document.createElement('div');
      toast.className = `toast toast--${type}`;
      toast.setAttribute('role', 'alert');

      const effectiveDuration = duration || (type === 'error' || type === 'warning' ? 4000 : 2500);

      const icon = this._createIcon(type);
      const msgSpan = document.createElement('span');
      msgSpan.className = 'toast__message';
      msgSpan.textContent = message;
      const closeBtn = this._createCloseBtn();

      toast.append(icon, msgSpan, closeBtn);
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

      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearTimeout(timer);
        dismiss();
      });

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
          btn.setAttribute('hidden', '');
          btn.hidden = true;
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
            btn.setAttribute('hidden', '');
            btn.hidden = true;
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
