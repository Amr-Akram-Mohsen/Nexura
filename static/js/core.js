/**
 * Nexura Phase 7 — Core JavaScript (core.js)
 * §24 — Single document-level event delegation, dark mode toggle, hero carousel,
 * progressive reveal, toast notifications, newsletter subscribe AJAX,
 * IntersectionObserver view tracking, CSRF token helper.
 */

'use strict';

// ─── CSRF ───────────────────────────────────────────────────────────────────
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

// ─── Toast System ────────────────────────────────────────────────────────────
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

  show(message, type = 'info', duration = 3500) {
    const c = this._getContainer();
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.setAttribute('role', 'alert');

    const icons = {
      success: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`,
      error:   `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
      info:    `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    };

    toast.innerHTML = `${icons[type] || icons.info}<span>${message}</span>`;
    c.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('toast--exit');
      toast.addEventListener('animationend', () => toast.remove(), { once: true });
    }, duration);
  },
};

// ─── Theme Toggle ────────────────────────────────────────────────────────────
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
      btn.innerHTML = theme === 'dark'
        ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`
        : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
    }
  },
};

// ─── Hero Carousel ───────────────────────────────────────────────────────────
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

// ─── Progressive Reveal ───────────────────────────────────────────────────────
const ProgressiveReveal = {
  init(containerSelector = '.grid-cards[data-reveal]', btnSelector = '[data-reveal-trigger]') {
    const containers = document.querySelectorAll(containerSelector);
    containers.forEach(container => {
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

// ─── IntersectionObserver — View Tracking ───────────────────────────────────
const ViewTracker = {
  observer: null,
  seen: new Set(),

  init() {
    if (!('IntersectionObserver' in window)) return;

    this.observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && entry.intersectionRatio >= 0.6) {
          const contentId = entry.target.dataset.contentId;
          if (contentId && !this.seen.has(contentId)) {
            this.seen.add(contentId);
            this.observer.unobserve(entry.target);
            this._recordImpression(contentId);
          }
        }
      });
    }, { threshold: 0.6 });

    document.querySelectorAll('[data-content-id]').forEach(el => {
      this.observer.observe(el);
    });
  },

  _recordImpression(contentId) {
    navigator.sendBeacon('/handle-interaction', new URLSearchParams({
      content_id: contentId,
      action: 'impression',
      csrf_token: getCsrfToken(),
    }));
  },
};

// ─── Mobile Nav ───────────────────────────────────────────────────────────────
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

// ─── Global Event Delegation (§24 — exactly 1 listener) ─────────────────────
document.addEventListener('click', (e) => {
  const target = e.target;

  // Theme toggle
  if (target.closest('[data-action="toggle-theme"]')) {
    ThemeManager.toggle();
    return;
  }

  // Hero dot navigation
  const dot = target.closest('.hero__dot');
  if (dot) {
    const idx = parseInt(dot.dataset.idx, 10);
    if (!isNaN(idx)) HeroCarousel.goto(idx);
    return;
  }

  // Mobile nav burger
  if (target.closest('[data-action="toggle-nav"]')) {
    // handled separately
    return;
  }

  // Interaction buttons (like, dislike, save, share)
  const interactionBtn = target.closest('[data-interaction]');
  if (interactionBtn) {
    e.preventDefault();
    const action   = interactionBtn.dataset.interaction;
    const contentId = interactionBtn.dataset.contentId;
    if (contentId) handleInteraction(action, contentId, interactionBtn);
    return;
  }

  // Newsletter subscribe
  const subBtn = target.closest('[data-action="subscribe"]');
  if (subBtn) {
    e.preventDefault();
    const form = subBtn.closest('form[data-subscribe-form]');
    if (form) handleSubscribe(form, subBtn);
    return;
  }

  // Copy link share button
  if (target.closest('[data-action="copy-link"]')) {
    e.preventDefault();
    navigator.clipboard.writeText(window.location.href).then(() => {
      Toast.show('Link copied to clipboard!', 'success');
    });
    return;
  }
});

// ─── Handle Interaction (Like, Dislike, Save, Share) ────────────────────────
async function handleInteraction(action, contentId, btn) {
  btn.disabled = true;
  try {
    const res = await fetch('/handle-interaction', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': getCsrfToken(),
      },
      body: new URLSearchParams({ action, content_id: contentId }),
    });

    if (res.status === 401) {
      Toast.show('Please log in to interact with content.', 'info');
      return;
    }

    const data = await res.json();
    if (data.success) {
      // Toggle active state
      if (action === 'like' || action === 'dislike') {
        const bar = btn.closest('.interaction-bar');
        if (bar) {
          bar.querySelectorAll('[data-interaction="like"], [data-interaction="dislike"]')
             .forEach(b => b.classList.remove('active'));
        }
        if (data.toggled) btn.classList.add('active');
      } else if (action === 'save') {
        btn.classList.toggle('active', data.saved);
        Toast.show(data.saved ? 'Saved to your library!' : 'Removed from library.', 'success');
      }

      // Update counter in UI
      const counter = btn.querySelector('[data-count]');
      if (counter && data.count !== undefined) {
        counter.textContent = data.count;
      }
    } else {
      Toast.show(data.message || 'Something went wrong.', 'error');
    }
  } catch {
    Toast.show('Could not complete action. Try again.', 'error');
  } finally {
    btn.disabled = false;
  }
}

// ─── Newsletter Subscribe ────────────────────────────────────────────────────
async function handleSubscribe(form, btn) {
  const input = form.querySelector('input[type="email"]');
  const email = input ? input.value.trim() : '';
  if (!email || !email.includes('@')) {
    Toast.show('Please enter a valid email address.', 'error');
    return;
  }

  const originalText = btn.textContent;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span>`;

  try {
    const res = await fetch('/subscribe', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': getCsrfToken(),
      },
      body: new URLSearchParams({ email }),
    });

    const data = await res.json();
    if (data.success) {
      Toast.show('Thank you! Please check your inbox to confirm.', 'success');
      form.reset();
    } else {
      Toast.show(data.message || 'Subscription failed. Try again.', 'error');
    }
  } catch {
    Toast.show('Network error. Please try again.', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
}

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  ThemeManager.init();
  HeroCarousel.init(document.querySelector('.hero-carousel'));
  ProgressiveReveal.init('.grid-cards[data-reveal]', '[data-reveal-trigger]');
  ViewTracker.init();
  initMobileNav();
});
