/**
 * Nexura — Article Chrome & Engagement Feature (features/article-chrome.js)
 * Manages the reading progress percentage pill, the sticky action pill bar,
 * the accessible social share modal (focus trapping & scroll locking), and impression tracking.
 */
'use strict';

(function () {
  window.Nexura = window.Nexura || {};

  function notify(msg, type = 'info', duration = null, title = null) {
    if (window.Nexura.toast) {
      window.Nexura.toast(msg, type, duration, title);
    } else if (window.Toast && typeof window.Toast.show === 'function') {
      window.Toast.show(msg, type, duration, title);
    }
  }

  function lockScroll() {
    if (window.Nexura.dom && typeof window.Nexura.dom.lockScroll === 'function') {
      window.Nexura.dom.lockScroll();
    } else {
      document.body.style.overflow = 'hidden';
    }
  }

  function unlockScroll() {
    if (window.Nexura.dom && typeof window.Nexura.dom.unlockScroll === 'function') {
      window.Nexura.dom.unlockScroll();
    } else {
      document.body.style.overflow = '';
    }
  }

  /* ── Reading Progress Pill Badge ─────────────────────────────────────────── */
  const ReadingProgress = {
    articleBody: null,
    badge: null,
    rafId: null,

    init() {
      this.articleBody = document.querySelector('.article-body, .article-html');
      this.badge = document.querySelector('.pill-progress-badge');
      if (!this.articleBody || !this.badge) return;

      const onScroll = () => {
        if (this.rafId) return;
        this.rafId = requestAnimationFrame(() => {
          this._update();
          this.rafId = null;
        });
      };
      window.addEventListener('scroll', onScroll, { passive: true });
      this._update();
    },

    _update() {
      if (!this.articleBody || !this.badge) return;
      const rect = this.articleBody.getBoundingClientRect();
      const docEl = document.documentElement;
      const winH = window.innerHeight || docEl.clientHeight;

      // Progress is 0→1 over the article body scroll range
      const total = rect.height;
      const scrolled = Math.max(0, -rect.top + winH * 0.15);
      const ratio = Math.min(1, Math.max(0, scrolled / total));

      const pct = Math.round(ratio * 100);
      this.badge.textContent = `${pct}% read`;
    },
  };

  /* ── Share Modal ─────────────────────────────────────────────────────────── */
  const ShareModal = {
    backdrop: null,
    focusableEls: [],
    _prevFocus: null,

    init() {
      this.backdrop = document.getElementById('share-modal');
      if (!this.backdrop) return;

      const card = this.backdrop.querySelector('.share-modal-card');
      if (!card) return;

      // Close triggers
      this.backdrop.addEventListener('click', (e) => {
        if (e.target === this.backdrop) this.close();
      });
      const closeBtn = this.backdrop.querySelector('.share-modal-card__close');
      if (closeBtn) closeBtn.addEventListener('click', () => this.close());

      // Escape key
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.backdrop.classList.contains('is-open')) this.close();
      });

      // Copy link button
      const copyBtn = this.backdrop.querySelector('.share-copy-btn');
      if (copyBtn) {
        copyBtn.addEventListener('click', () => {
          const url = window.location.href;
          navigator.clipboard
            .writeText(url)
            .then(() => {
              notify('Link copied to clipboard!', 'success', 3000, 'Copied');
              this.close();
            })
            .catch(() => {
              // Fallback
              const ta = document.createElement('textarea');
              ta.value = url;
              document.body.appendChild(ta);
              ta.select();
              document.execCommand('copy');
              ta.remove();
              notify('Link copied!', 'success', 3000, 'Copied');
              this.close();
            });
        });
      }

      // Open triggers anywhere on the page
      document.addEventListener('click', (e) => {
        const trigger = e.target.closest('[data-action="open-share"]');
        if (trigger) {
          e.preventDefault();
          this.open();
        }
      });
    },

    open() {
      if (!this.backdrop) return;
      this._prevFocus = document.activeElement;

      // Update the URL displayed in copy row
      const urlEl = this.backdrop.querySelector('.share-copy-url');
      if (urlEl) urlEl.textContent = window.location.href;

      // Update social links
      const title = encodeURIComponent(document.title);
      const url = encodeURIComponent(window.location.href);
      const links = {
        twitter: `https://twitter.com/intent/tweet?text=${title}&url=${url}`,
        linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${url}`,
        whatsapp: `https://api.whatsapp.com/send?text=${title}%20${url}`,
        reddit: `https://reddit.com/submit?url=${url}&title=${title}`,
      };
      Object.entries(links).forEach(([platform, href]) => {
        const el = this.backdrop.querySelector(`[data-platform="${platform}"]`);
        if (el) el.href = href;
      });

      this.backdrop.classList.add('is-open');
      lockScroll();

      // Trap focus
      this.focusableEls = Array.from(
        this.backdrop.querySelectorAll('button, [href], input, [tabindex]:not([tabindex="-1"])')
      ).filter((el) => !el.disabled);
      if (this.focusableEls.length) this.focusableEls[0].focus();
    },

    close() {
      if (!this.backdrop) return;
      this.backdrop.classList.remove('is-open');
      unlockScroll();
      if (this._prevFocus && typeof this._prevFocus.focus === 'function') {
        this._prevFocus.focus();
      }
    },
  };

  /* ── Sticky Action Pill ──────────────────────────────────────────────────── */
  const StickyActionPill = {
    pill: null,
    triggerEl: null,
    observer: null,

    init() {
      this.pill = document.getElementById('sticky-action-pill');
      if (!this.pill) return;
      this.triggerEl = document.querySelector('.interaction-bar');
      if (!this.triggerEl) return;

      const updateVisibility = () => {
        if (!this.pill || !this.triggerEl) return;
        const rect = this.triggerEl.getBoundingClientRect();
        const isPast = rect.bottom < 50;
        this.pill.classList.toggle('is-visible', isPast);
      };

      this.observer = new IntersectionObserver(
        () => {
          updateVisibility();
        },
        { threshold: [0, 1], rootMargin: '-50px 0px 0px 0px' }
      );
      this.observer.observe(this.triggerEl);

      window.addEventListener(
        'scroll',
        () => {
          requestAnimationFrame(updateVisibility);
        },
        { passive: true }
      );

      updateVisibility();

      // Wire pill buttons → sync with static bar
      this.pill.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-pill-action]');
        if (!btn) return;
        const action = btn.dataset.pillAction;

        if (action === 'share') {
          ShareModal.open();
          return;
        }
        if (action === 'comments') {
          const target = document.getElementById('comments');
          if (target) target.scrollIntoView({ behavior: 'smooth' });
          return;
        }

        // Mirror click to the static interaction bar button
        const mirror = document.querySelector(`.interaction-bar [data-interaction="${action}"]`);
        if (mirror) {
          mirror.click();
          const isActive = mirror.classList.contains('active');
          btn.classList.toggle('active', isActive);
          const countEl = mirror.querySelector('[data-count]');
          const pillCount = btn.querySelector('[data-pill-count]');
          if (countEl && pillCount) pillCount.textContent = countEl.textContent;
        }
      });

      this._syncFromStaticBar();
      document.addEventListener('click', (e) => {
        if (e.target.closest('.interaction-bar')) {
          setTimeout(() => this._syncFromStaticBar(), 100);
        }
      });
    },

    _syncFromStaticBar() {
      if (!this.pill) return;
      ['like', 'save', 'dislike'].forEach((action) => {
        const staticBtn = document.querySelector(`.interaction-bar [data-interaction="${action}"]`);
        const pillBtn = this.pill.querySelector(`[data-pill-action="${action}"]`);
        if (staticBtn && pillBtn) {
          pillBtn.classList.toggle('active', staticBtn.classList.contains('active'));
          const countEl = staticBtn.querySelector('[data-count]');
          const pillCount = pillBtn.querySelector('[data-pill-count]');
          if (countEl && pillCount) pillCount.textContent = countEl.textContent;
        }
      });

      const staticCommentCount = document.querySelector('.interaction-bar [data-comment-count]');
      const pillCommentCount = this.pill.querySelector('[data-pill-comment-count]');
      if (staticCommentCount && pillCommentCount) {
        pillCommentCount.textContent = staticCommentCount.textContent;
      }
    },
  };

  /* ── View Tracker (Impression Logging) ───────────────────────────────────── */
  const ViewTracker = {
    observer: null,
    seen: new Set(),

    init() {
      if (!('IntersectionObserver' in window)) return;

      this.observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting && entry.intersectionRatio >= 0.6) {
              const contentId = entry.target.dataset.contentId;
              if (contentId && !this.seen.has(contentId)) {
                this.seen.add(contentId);
                this.observer.unobserve(entry.target);
                this._recordImpression(contentId);
              }
            }
          });
        },
        { threshold: 0.6 }
      );

      document.querySelectorAll('[data-content-id]').forEach((el) => {
        this.observer.observe(el);
      });
    },

    _recordImpression(contentId) {
      const csrf = window.Nexura.http
        ? window.Nexura.http.getCsrfToken()
        : document.querySelector('meta[name="csrf-token"]')?.content || '';
      navigator.sendBeacon(
        '/handle-interaction',
        new URLSearchParams({
          content_id: contentId,
          action: 'impression',
          csrf_token: csrf,
        })
      );
    },
  };

  // Delegated copy link handler
  document.addEventListener('click', (e) => {
    const copyLinkBtn = e.target.closest('[data-action="copy-link"]');
    if (copyLinkBtn) {
      e.preventDefault();
      navigator.clipboard.writeText(window.location.href).then(() => {
        notify('Link copied to clipboard!', 'success');
      });
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    ReadingProgress.init();
    StickyActionPill.init();
    ShareModal.init();
    ViewTracker.init();
  });

  window.Nexura.articleChrome = {
    ReadingProgress,
    StickyActionPill,
    ShareModal,
    ViewTracker,
  };
})();
