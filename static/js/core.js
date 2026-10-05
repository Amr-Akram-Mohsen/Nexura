/** Core client interactions, navigation, toasts, and comments. */
'use strict';

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

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
      remaining -= (Date.now() - startTime);
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

function mountVideoFacade(facade) {
  if (!facade || facade.dataset.mounted === 'true') return;
  const videoId = facade.dataset.videoId;
  if (!videoId) return;

  const thumb = facade.querySelector('.video-facade__thumb');
  const playEl = facade.querySelector('.video-facade__play');
  const durationEl = facade.querySelector('.video-facade__duration');

  if (thumb) thumb.style.display = 'none';
  if (playEl) playEl.style.display = 'none';
  if (durationEl) durationEl.style.display = 'none';

  const iframe = document.createElement('iframe');
  iframe.setAttribute('allow', 'autoplay; encrypted-media; picture-in-picture; fullscreen');
  iframe.setAttribute('allowfullscreen', '');
  iframe.setAttribute('loading', 'lazy');
  iframe.setAttribute('title', facade.dataset.videoTitle || 'YouTube Video');
  iframe.src = `https://www.youtube.com/embed/${encodeURIComponent(videoId)}?autoplay=1&rel=0&modestbranding=1`;

  facade.appendChild(iframe);
  facade.dataset.mounted = 'true';
  facade.style.aspectRatio = '16/9';
}

window.mountVideoFacade = mountVideoFacade;

document.addEventListener('click', (e) => {
  const target = e.target;

  const facade = target.closest('.video-facade[data-video-id]');
  if (facade && facade.dataset.mounted !== 'true') {
    mountVideoFacade(facade);
    return;
  }

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

  const interactionBtn = target.closest('[data-interaction]');
  if (interactionBtn) {
    e.preventDefault();
    if (interactionBtn.disabled) return;
    const action = interactionBtn.dataset.interaction;
    const targetType = interactionBtn.dataset.targetType || 'content';
    const targetId = interactionBtn.dataset.targetId || interactionBtn.dataset.contentId;
    if (targetId) handleInteraction(action, targetId, interactionBtn, targetType);
    return;
  }

  const subBtn = target.closest('[data-action="subscribe"]');
  if (subBtn) {
    e.preventDefault();
    const form = subBtn.closest('form[data-subscribe-form]');
    if (form) handleSubscribe(form, subBtn);
    return;
  }

  const unsubBtn = target.closest('[data-action="unsubscribe-newsletter"]');
  if (unsubBtn) {
    e.preventDefault();
    handleUnsubscribe(unsubBtn);
    return;
  }

  if (target.closest('[data-action="copy-link"]')) {
    e.preventDefault();
    navigator.clipboard.writeText(window.location.href).then(() => {
      Toast.show('Link copied to clipboard!', 'success');
    });
    return;
  }

  const scrollCommentsBtn = target.closest('[data-action="scroll-to-comments"], a[href="#comments"]');
  if (scrollCommentsBtn) {
    e.preventDefault();
    const commentsEl = document.getElementById('comments');
    if (commentsEl) {
      commentsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
      const input = commentsEl.querySelector('.comment-form__input');
      if (input) input.focus();
    }
    return;
  }

  const replyBtn = target.closest('[data-action="toggle-reply"]');
  if (replyBtn) {
    e.preventDefault();
    toggleReplyForm(replyBtn);
    return;
  }

  const repliesToggle = target.closest('[data-action="toggle-replies"]');
  if (repliesToggle) {
    e.preventDefault();
    const targetId = repliesToggle.dataset.target;
    const container = document.getElementById(targetId);
    if (!container) return;
    const isOpen = repliesToggle.getAttribute('aria-expanded') === 'true';
    if (isOpen) {
      container.style.display = 'none';
      container.setAttribute('aria-hidden', 'true');
      repliesToggle.setAttribute('aria-expanded', 'false');
    } else {
      container.style.display = 'flex';
      container.setAttribute('aria-hidden', 'false');
      repliesToggle.setAttribute('aria-expanded', 'true');
    }
    return;
  }

  const loadMoreBtn = target.closest('[data-action="load-more-comments"]');
  if (loadMoreBtn) {
    e.preventDefault();
    const BATCH = 10;
    const hidden = [...document.querySelectorAll('.comment-list__item--hidden')];
    const toShow = hidden.slice(0, BATCH);
    toShow.forEach(item => item.classList.remove('comment-list__item--hidden'));
    const remaining = hidden.length - toShow.length;
    if (remaining <= 0) {
      const loadMoreEl = document.getElementById('comments-load-more');
      if (loadMoreEl) loadMoreEl.style.display = 'none';
    } else {
      loadMoreBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>
        Show ${remaining} more ${remaining === 1 ? 'comment' : 'comments'}
      `;
    }
    return;
  }

  const cancelReplyBtn = target.closest('[data-action="cancel-reply"]');
  if (cancelReplyBtn) {
    e.preventDefault();
    const replyForm = cancelReplyBtn.closest('.comment-reply-form');
    if (replyForm) replyForm.remove();
    return;
  }
});

/* ════════════════════════════════════════════════════════════════════════════
   Auth Popover (Contextual micro-prompt for unauthenticated interactions)
   ════════════════════════════════════════════════════════════════════════════ */
let activeAuthPopover = null;

function showAuthPopover(btn, action = 'interact') {
  if (activeAuthPopover) {
    activeAuthPopover.dismiss();
  }

  const popover = document.createElement('div');
  popover.className = 'auth-popover';
  popover.setAttribute('role', 'dialog');
  popover.setAttribute('aria-label', 'Sign in required');

  const actionMap = {
    like: 'like this',
    dislike: 'react to this',
    save: 'save to library',
  };
  const actionText = actionMap[action] || 'interact';
  const returnUrl = encodeURIComponent(window.location.pathname + window.location.search);

  popover.innerHTML = `
    <div class="auth-popover__header">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
      </svg>
      <span>Sign in to ${actionText}</span>
    </div>
    <div class="auth-popover__actions">
      <a href="/auth/login?next=${returnUrl}" class="auth-popover__btn auth-popover__btn--login">Log In</a>
      <a href="/auth/register?next=${returnUrl}" class="auth-popover__btn auth-popover__btn--signup">Sign Up</a>
    </div>
  `;

  document.body.appendChild(popover);

  // Position relative to btn
  const btnRect = btn.getBoundingClientRect();
  const popoverRect = popover.getBoundingClientRect();

  let top = btnRect.top - 8;

  // If clipping the top viewport edge
  if (btnRect.top - popoverRect.height - 12 < 0) {
    top = btnRect.bottom + 8;
    popover.classList.add('auth-popover--bottom');
  }

  // Center horizontally over the trigger button, clamped to viewport margins
  let left = btnRect.left + (btnRect.width / 2);
  const halfWidth = popoverRect.width / 2;
  const margin = 12;
  if (left - halfWidth < margin) {
    left = margin + halfWidth;
  } else if (left + halfWidth > window.innerWidth - margin) {
    left = window.innerWidth - margin - halfWidth;
  }

  popover.style.top = `${Math.round(top)}px`;
  popover.style.left = `${Math.round(left)}px`;

  let dismissTimer = null;

  const dismiss = () => {
    if (dismissTimer) clearTimeout(dismissTimer);
    window.removeEventListener('scroll', dismiss, true);
    document.removeEventListener('click', outsideClick, true);
    document.removeEventListener('keydown', onKeyDown);

    if (popover && popover.parentNode) {
      popover.classList.add('auth-popover--exit');
      setTimeout(() => {
        if (popover.parentNode) popover.remove();
        if (activeAuthPopover && activeAuthPopover.el === popover) {
          activeAuthPopover = null;
        }
      }, 160);
    }
  };

  const outsideClick = (e) => {
    if (!popover.contains(e.target) && !btn.contains(e.target)) {
      dismiss();
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Escape') {
      dismiss();
    }
  };

  dismissTimer = setTimeout(dismiss, 3500);

  setTimeout(() => {
    document.addEventListener('click', outsideClick, true);
    window.addEventListener('scroll', dismiss, { capture: true, passive: true, once: true });
    document.addEventListener('keydown', onKeyDown);
  }, 20);

  activeAuthPopover = { el: popover, dismiss };
}

async function handleInteraction(action, targetId, btn, targetType = 'content') {
  btn.disabled = true;
  try {
    const res = await fetch('/handle-interaction', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': getCsrfToken(),
      },
      body: new URLSearchParams({
        action,
        content_id: targetId,
        target_id: targetId,
        target_type: targetType,
      }),
    });

    if (res.status === 401) {
      showAuthPopover(btn, action);
      return;
    }

    const data = await res.json();
    if (data.success) {
      if (targetType === 'comment') {
        const commentCard = btn.closest('.comment-card');
        if (commentCard) {
          const likeBtn = commentCard.querySelector('.comment-action-btn[data-interaction="like"]');
          const dislikeBtn = commentCard.querySelector('.comment-action-btn[data-interaction="dislike"]');

          const isLiked = data.liked !== undefined ? data.liked : (action === 'like' && data.toggled);
          const isDisliked = data.disliked !== undefined ? data.disliked : (action === 'dislike' && data.toggled);

          if (likeBtn) {
            likeBtn.classList.toggle('active', isLiked);
            likeBtn.setAttribute('aria-pressed', isLiked ? 'true' : 'false');
            const svg = likeBtn.querySelector('svg');
            if (svg) svg.setAttribute('fill', isLiked ? 'currentColor' : 'none');
            const countEl = likeBtn.querySelector('[data-count]');
            if (countEl && data.like_count !== undefined) countEl.textContent = data.like_count;
          }

          if (dislikeBtn) {
            dislikeBtn.classList.toggle('active', isDisliked);
            dislikeBtn.classList.toggle('dislike', isDisliked);
            dislikeBtn.setAttribute('aria-pressed', isDisliked ? 'true' : 'false');
            const svg = dislikeBtn.querySelector('svg');
            if (svg) svg.setAttribute('fill', isDisliked ? 'currentColor' : 'none');
            const countEl = dislikeBtn.querySelector('[data-count]');
            if (countEl && data.dislike_count !== undefined) countEl.textContent = data.dislike_count;
          }
        }
      } else {
        const bar = btn.closest('.interaction-bar') || document.querySelector(`.interaction-bar[data-content-id="${targetId}"]`);

        if (action === 'like' || action === 'dislike') {
          const likeBtn = bar ? bar.querySelector('[data-interaction="like"]') : (action === 'like' ? btn : null);
          const dislikeBtn = bar ? bar.querySelector('[data-interaction="dislike"]') : (action === 'dislike' ? btn : null);

          const isLiked = data.liked !== undefined ? data.liked : (action === 'like' && data.toggled);
          const isDisliked = data.disliked !== undefined ? data.disliked : (action === 'dislike' && data.toggled);

          if (likeBtn) {
            likeBtn.classList.toggle('active', isLiked);
            likeBtn.setAttribute('aria-pressed', isLiked ? 'true' : 'false');
            const svg = likeBtn.querySelector('svg');
            if (svg) svg.setAttribute('fill', isLiked ? 'currentColor' : 'none');

            const likeCountEl = likeBtn.querySelector('[data-count]');
            if (likeCountEl && data.like_count !== undefined) {
              likeCountEl.textContent = data.like_count;
            } else if (likeCountEl && action === 'like' && data.count !== undefined) {
              likeCountEl.textContent = data.count;
            }
          }

          if (dislikeBtn) {
            dislikeBtn.classList.toggle('active', isDisliked);
            dislikeBtn.classList.toggle('dislike', isDisliked);
            dislikeBtn.setAttribute('aria-pressed', isDisliked ? 'true' : 'false');
            const svg = dislikeBtn.querySelector('svg');
            if (svg) svg.setAttribute('fill', isDisliked ? 'currentColor' : 'none');

            const dislikeCountEl = dislikeBtn.querySelector('[data-count]');
            if (dislikeCountEl && data.dislike_count !== undefined) {
              dislikeCountEl.textContent = data.dislike_count;
            } else if (dislikeCountEl && action === 'dislike' && data.count !== undefined) {
              dislikeCountEl.textContent = data.count;
            }
          }
        } else if (action === 'save') {
          const isSaved = data.saved !== undefined ? data.saved : data.toggled;
          btn.classList.toggle('active', isSaved);
          btn.setAttribute('aria-pressed', isSaved ? 'true' : 'false');
          const svg = btn.querySelector('svg');
          if (svg) svg.setAttribute('fill', isSaved ? 'currentColor' : 'none');

          const spanText = btn.querySelector('span:not([data-count])');
          if (spanText) {
            spanText.textContent = isSaved ? 'Saved' : 'Save';
          } else {
            const textNode = Array.from(btn.childNodes).find(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
            if (textNode) {
              textNode.textContent = isSaved ? ' Saved' : ' Save';
            }
          }
        }
      }
    } else {
      Toast.show(data.message || 'Something went wrong.', 'error');
    }
  } catch (err) {
    Toast.show('Could not complete action. Try again.', 'error');
  } finally {
    btn.disabled = false;
  }
}

const newsletterChannel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('nexura_newsletter_sync') : null;

function broadcastNewsletterState(isSubscribed, email) {
  if (newsletterChannel) {
    try {
      newsletterChannel.postMessage({ type: 'newsletter_state_changed', isSubscribed, email });
    } catch {}
  }
  try {
    localStorage.setItem('nexura_newsletter_sync', JSON.stringify({ isSubscribed, email, time: Date.now() }));
  } catch {}
}

function syncNewsletterBoxesAcrossUI(isSubscribed, email) {
  document.querySelectorAll('[data-newsletter-box]').forEach(box => {
    const stateSub = box.querySelector('[data-newsletter-subscribed]');
    const stateForm = box.querySelector('[data-newsletter-form-container]');
    const emailEl = box.querySelector('[data-newsletter-email]');
    if (email && emailEl) emailEl.textContent = email;

    if (stateSub && stateForm) {
      if (isSubscribed) {
        stateForm.classList.add('is-hidden');
        stateSub.classList.remove('is-hidden');
      } else {
        stateSub.classList.add('is-hidden');
        stateForm.classList.remove('is-hidden');
        const input = stateForm.querySelector('input[name="email"], input[type="email"]');
        if (input && email && !input.value) {
          input.value = email;
        }
        const authEmailEl = stateForm.querySelector('[data-newsletter-auth-email]');
        if (authEmailEl && email && !authEmailEl.textContent.trim()) {
          authEmailEl.textContent = email;
        }
      }
    }
  });
}

if (newsletterChannel) {
  newsletterChannel.onmessage = (e) => {
    if (e.data && e.data.type === 'newsletter_state_changed') {
      syncNewsletterBoxesAcrossUI(e.data.isSubscribed, e.data.email);
    }
  };
}

window.addEventListener('storage', (e) => {
  if (e.key === 'nexura_newsletter_sync' && e.newValue) {
    try {
      const data = JSON.parse(e.newValue);
      syncNewsletterBoxesAcrossUI(data.isSubscribed, data.email);
    } catch {}
  }
});

async function handleSubscribe(form, btn) {
  const input = form.querySelector('input[name="email"], input[type="email"]');
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
      Toast.show(data.message || 'Thank you! Please check your inbox to confirm.', 'success');
      if (data.is_confirmed || data.already_subscribed) {
        syncNewsletterBoxesAcrossUI(true, data.email || email);
        broadcastNewsletterState(true, data.email || email);
      }
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

async function handleUnsubscribe(btn) {
  const box = btn.closest('[data-newsletter-box]');
  const emailEl = box ? box.querySelector('[data-newsletter-email]') : null;
  const email = emailEl ? emailEl.textContent.trim() : '';

  const originalText = btn.textContent;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span>`;

  try {
    const res = await fetch('/unsubscribe', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': getCsrfToken(),
      },
      body: new URLSearchParams({ email }),
    });

    const data = await res.json();
    if (data.success) {
      Toast.show(data.message || 'You have been unsubscribed.', 'success');
      syncNewsletterBoxesAcrossUI(false, email);
      broadcastNewsletterState(false, email);
    } else {
      Toast.show(data.message || 'Could not unsubscribe. Please try again.', 'error');
    }
  } catch {
    Toast.show('Network error. Please try again.', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
}



function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function toggleReplyForm(replyBtn) {
  const parentId = replyBtn.dataset.parentId;
  const contentId = replyBtn.dataset.contentId;
  const slot = document.getElementById(`reply-slot-${parentId}`);
  if (!slot) return;

  const existing = slot.querySelector('.comment-reply-form');
  if (existing) {
    existing.remove();
    return;
  }

  document.querySelectorAll('.comment-reply-form').forEach(f => f.remove());

  const form = document.createElement('form');
  form.className = 'comment-reply-form';
  form.setAttribute('data-comment-form', '');
  form.setAttribute('data-content-id', contentId);
  form.innerHTML = `
    <input type="hidden" name="content_id" value="${encodeURIComponent(contentId)}">
    <input type="hidden" name="parent_id" value="${encodeURIComponent(parentId)}">
    <textarea name="text" placeholder="Write a reply..." rows="2" maxlength="2000" required></textarea>
    <div class="comment-reply-form__actions">
      <button class="btn btn--ghost btn--sm" type="button" data-action="cancel-reply">Cancel</button>
      <button class="btn btn--gradient btn--sm" type="submit">Reply</button>
    </div>
  `;
  slot.appendChild(form);
  const textarea = form.querySelector('textarea');
  if (textarea) textarea.focus();
}

async function handleCommentSubmit(form) {
  const submitBtn = form.querySelector('button[type="submit"]');
  const textarea = form.querySelector('textarea[name="text"]');
  const text = textarea ? textarea.value.trim() : '';

  if (!text || text.length < 2) {
    Toast.show('Comment must be at least 2 characters.', 'error');
    if (textarea) textarea.focus();
    return;
  }

  const contentId = form.dataset.contentId || form.querySelector('input[name="content_id"]')?.value;
  const parentIdInput = form.querySelector('input[name="parent_id"]');
  const parentId = parentIdInput ? parentIdInput.value : null;

  if (!contentId) {
    Toast.show('Missing content ID.', 'error');
    return;
  }

  const originalBtnHtml = submitBtn ? submitBtn.innerHTML : '';
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span>';
  }

  try {
    const params = new URLSearchParams({
      content_id: contentId,
      text: text,
    });
    if (parentId) {
      params.append('parent_id', parentId);
    }

    const res = await fetch('/comments/submit', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': getCsrfToken(),
      },
      body: params,
    });

    if (res.status === 401) {
      Toast.show('Please log in to post a comment.', 'info');
      return;
    }

    const data = await res.json();
    if (data.success && data.comment) {
      const c = data.comment;
      const initial = (c.user_name || 'C')[0].toUpperCase();

      const cardHtml = `
        <div class="comment-card ${parentId ? 'comment-card--reply' : ''}" id="comment-${c.id}" data-comment-id="${c.id}" data-user-id="${c.user_id}">
          <div class="comment-card__avatar" aria-hidden="true">${escapeHtml(initial)}</div>
          <div class="comment-card__body">
            <div class="comment-card__header">
              <span class="comment-card__author">${escapeHtml(c.user_name || 'Community Member')}</span>
              <span class="comment-card__badge-you">You</span>
              <time class="comment-card__date">${escapeHtml(c.formatted_date || 'Just now')}</time>
            </div>
            <p class="comment-card__text">${escapeHtml(c.content)}</p>
            <div class="comment-card__actions">
              <button class="comment-action-btn" data-interaction="like" data-target-type="comment" data-target-id="${c.id}" disabled title="You cannot react to your own comment" aria-disabled="true" type="button">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z" />
                  <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
                </svg>
                <span data-count>0</span>
              </button>
              <button class="comment-action-btn" data-interaction="dislike" data-target-type="comment" data-target-id="${c.id}" disabled title="You cannot react to your own comment" aria-disabled="true" type="button">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z" />
                  <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
                </svg>
                <span data-count>0</span>
              </button>
            </div>
            ${!parentId ? `
            <div class="comment-reply-slot" id="reply-slot-${c.id}"></div>
            <div class="comment-card__replies" id="replies-${c.id}" style="display:none;"></div>
            ` : ''}
          </div>
        </div>
      `;

      if (parentId) {
        const parentCard = document.getElementById(`comment-${parentId}`);
        let repliesContainer = document.getElementById(`replies-${parentId}`);
        if (!repliesContainer && parentCard) {
          repliesContainer = document.createElement('div');
          repliesContainer.className = 'comment-card__replies';
          repliesContainer.id = `replies-${parentId}`;
          repliesContainer.setAttribute('aria-hidden', 'false');
          parentCard.querySelector('.comment-card__body').appendChild(repliesContainer);
        }
        if (repliesContainer) {
          repliesContainer.style.display = 'flex';
          repliesContainer.setAttribute('aria-hidden', 'false');
          repliesContainer.insertAdjacentHTML('beforeend', cardHtml);
        }
        // Update or create the replies toggle button
        const existingToggle = parentCard ? parentCard.querySelector('.comment-replies-toggle[data-target="replies-' + parentId + '"]') : null;
        if (existingToggle) {
          existingToggle.setAttribute('aria-expanded', 'true');
          const countEl = existingToggle.querySelector('span');
          if (countEl) {
            const currentCount = parseInt(countEl.textContent) || 0;
            const newCount = currentCount + 1;
            countEl.textContent = `${newCount} ${newCount === 1 ? 'reply' : 'replies'}`;
          }
        } else if (parentCard) {
          // First reply — create the toggle button before the replies container
          const toggleBtn = document.createElement('button');
          toggleBtn.className = 'comment-replies-toggle';
          toggleBtn.type = 'button';
          toggleBtn.dataset.action = 'toggle-replies';
          toggleBtn.dataset.target = `replies-${parentId}`;
          toggleBtn.setAttribute('aria-expanded', 'true');
          toggleBtn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg><span>1 reply</span>`;
          repliesContainer.parentNode.insertBefore(toggleBtn, repliesContainer);
        }
        form.remove();
      } else {
        const list = document.getElementById('comment-list');
        if (list) {
          const wrapper = document.createElement('div');
          wrapper.className = 'comment-list__item';
          wrapper.innerHTML = cardHtml;
          list.insertAdjacentElement('afterbegin', wrapper);
        }
        const emptyState = document.getElementById('comments-empty');
        if (emptyState) emptyState.style.display = 'none';

        form.reset();
        const charCount = form.querySelector('[data-char-count]');
        if (charCount) charCount.textContent = '0';
      }

      if (data.comment_count !== undefined) {
        document.querySelectorAll('[data-comment-count]').forEach(el => {
          el.textContent = data.comment_count;
        });
      }
    } else {
      Toast.show(data.message || 'Could not post comment.', 'error');
    }
  } catch (err) {
    Toast.show('Network error. Could not post comment.', 'error');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalBtnHtml;
    }
  }
}

document.addEventListener('submit', async (e) => {
  const subForm = e.target.closest('form[data-subscribe-form]');
  if (subForm) {
    e.preventDefault();
    const btn = subForm.querySelector('[data-action="subscribe"], button[type="submit"]');
    await handleSubscribe(subForm, btn);
    return;
  }

  const commentForm = e.target.closest('[data-comment-form]');
  if (commentForm) {
    e.preventDefault();
    await handleCommentSubmit(commentForm);
  }
});

document.addEventListener('input', (e) => {
  const textarea = e.target.closest('.comment-form__input, .comment-reply-form textarea');
  if (textarea) {
    const form = textarea.closest('form');
    const counter = form ? form.querySelector('[data-char-count]') : null;
    if (counter) {
      counter.textContent = textarea.value.length;
    }
  }

  // Auto-grow any comment textarea
  const growable = e.target.closest('.comment-form__input');
  if (growable) {
    const MAX_H = 105; // ~5 lines
    growable.style.height = 'auto';
    const next = Math.min(growable.scrollHeight, MAX_H);
    growable.style.height = next + 'px';
    growable.style.overflowY = growable.scrollHeight > MAX_H ? 'auto' : 'hidden';
  }
});

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

function initAlertDismissals() {
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.alert__close, [data-action="dismiss-alert"]');
    if (!btn) return;

    e.preventDefault();
    const alert = btn.closest('.alert');
    if (!alert) return;

    alert.classList.add('alert--collapsing');
    alert.addEventListener('transitionend', () => {
      alert.remove();
    }, { once: true });

    // Fallback in case transitionend does not fire
    setTimeout(() => {
      if (alert.parentNode) {
        alert.remove();
      }
    }, 350);
  });
}

function initFlashedMessages() {
  const el = document.getElementById('flashed-messages-data');
  if (!el) return;

  try {
    const raw = el.getAttribute('data-messages');
    if (!raw) return;
    const messages = JSON.parse(raw);
    messages.forEach(([category, message], index) => {
      setTimeout(() => {
        const type = (category === 'error' || category === 'danger')
          ? 'error'
          : (category === 'success' ? 'success' : (category === 'warning' ? 'warning' : 'info'));
        Toast.show(message, type);
      }, index * 250);
    });
  } catch (err) {
    console.error('Failed to parse flashed messages:', err);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  ThemeManager.init();
  HeroCarousel.init(document.querySelector('.hero-carousel'));
  ProgressiveReveal.init('.grid-cards[data-reveal]', '[data-reveal-trigger]');
  ViewTracker.init();
  initMobileNav();
  initPasswordToggles();
  initAlertDismissals();
  initFlashedMessages();
  ReadingProgress.init();
  StickyActionPill.init();
  ShareModal.init();
  initCommentExpands();
});

/* ════════════════════════════════════════════════════════════════════════════
   Reading Progress Pill Badge
   ════════════════════════════════════════════════════════════════════════════ */
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

/* ════════════════════════════════════════════════════════════════════════════
   Comment Text Expand Toggles
   ════════════════════════════════════════════════════════════════════════════ */
function initCommentExpands() {
  document.querySelectorAll('.comment-card__expand-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const text = btn.previousElementSibling;
      if (!text) return;
      const isClamped = text.classList.toggle('comment-card__text--clamped');
      btn.textContent = isClamped ? 'Show more' : 'Show less';
      btn.setAttribute('aria-expanded', isClamped ? 'false' : 'true');
    });
  });
}

/* ════════════════════════════════════════════════════════════════════════════
   Share Modal
   ════════════════════════════════════════════════════════════════════════════ */
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
        navigator.clipboard.writeText(url).then(() => {
          Toast.show('Link copied to clipboard!', 'success', 3000, 'Copied');
          this.close();
        }).catch(() => {
          // Fallback
          const ta = document.createElement('textarea');
          ta.value = url;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          ta.remove();
          Toast.show('Link copied!', 'success', 3000, 'Copied');
          this.close();
        });
      });
    }

    // Open triggers anywhere on the page
    document.addEventListener('click', (e) => {
      const trigger = e.target.closest('[data-action="open-share"]');
      if (trigger) { e.preventDefault(); this.open(); }
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
      twitter:  `https://twitter.com/intent/tweet?text=${title}&url=${url}`,
      linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${url}`,
      whatsapp: `https://api.whatsapp.com/send?text=${title}%20${url}`,
      reddit:   `https://reddit.com/submit?url=${url}&title=${title}`,
    };
    Object.entries(links).forEach(([platform, href]) => {
      const el = this.backdrop.querySelector(`[data-platform="${platform}"]`);
      if (el) el.href = href;
    });

    this.backdrop.classList.add('is-open');
    document.body.style.overflow = 'hidden';

    // Trap focus
    this.focusableEls = Array.from(
      this.backdrop.querySelectorAll('button, [href], input, [tabindex]:not([tabindex="-1"])')
    ).filter(el => !el.disabled);
    if (this.focusableEls.length) this.focusableEls[0].focus();
  },

  close() {
    if (!this.backdrop) return;
    this.backdrop.classList.remove('is-open');
    document.body.style.overflow = '';
    if (this._prevFocus) this._prevFocus.focus();
  },
};

/* ════════════════════════════════════════════════════════════════════════════
   Sticky Action Pill
   ════════════════════════════════════════════════════════════════════════════ */
const StickyActionPill = {
  pill: null,
  triggerEl: null,   // The static interaction-bar
  observer: null,

  init() {
    this.pill = document.getElementById('sticky-action-pill');
    if (!this.pill) return;
    this.triggerEl = document.querySelector('.interaction-bar');
    if (!this.triggerEl) return;

    // Show pill ONLY once the static bar has scrolled out of view ABOVE the viewport
    const updateVisibility = () => {
      if (!this.pill || !this.triggerEl) return;
      const rect = this.triggerEl.getBoundingClientRect();
      // rect.bottom < 50 means the bottom of the interaction bar is at or above the top navbar
      const isPast = rect.bottom < 50;
      this.pill.classList.toggle('is-visible', isPast);
    };

    // IntersectionObserver triggers when the interaction bar crosses the viewport threshold
    this.observer = new IntersectionObserver(() => {
      updateVisibility();
    }, { threshold: [0, 1], rootMargin: '-50px 0px 0px 0px' });
    this.observer.observe(this.triggerEl);

    // Scroll listener ensures immediate sync during rapid scrolls
    window.addEventListener('scroll', () => {
      requestAnimationFrame(updateVisibility);
    }, { passive: true });

    // Initial check (starts hidden if interaction bar is below or in viewport)
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
      const mirror = document.querySelector(
        `.interaction-bar [data-interaction="${action}"]`
      );
      if (mirror) {
        mirror.click();
        // Sync active state back to pill button
        const isActive = mirror.classList.contains('active');
        btn.classList.toggle('active', isActive);
        const countEl = mirror.querySelector('[data-count]');
        const pillCount = btn.querySelector('[data-pill-count]');
        if (countEl && pillCount) pillCount.textContent = countEl.textContent;
      }
    });

    // Sync active states from static bar → pill on load & after interactions
    this._syncFromStaticBar();
    document.addEventListener('click', (e) => {
      if (e.target.closest('.interaction-bar')) {
        setTimeout(() => this._syncFromStaticBar(), 100);
      }
    });
  },

  _syncFromStaticBar() {
    if (!this.pill) return;
    ['like', 'save', 'dislike'].forEach(action => {
      const staticBtn = document.querySelector(`.interaction-bar [data-interaction="${action}"]`);
      const pillBtn   = this.pill.querySelector(`[data-pill-action="${action}"]`);
      if (staticBtn && pillBtn) {
        pillBtn.classList.toggle('active', staticBtn.classList.contains('active'));
        const countEl   = staticBtn.querySelector('[data-count]');
        const pillCount = pillBtn.querySelector('[data-pill-count]');
        if (countEl && pillCount) pillCount.textContent = countEl.textContent;
      }
    });
    // Comments count
    const staticCommentCount = document.querySelector('.interaction-bar [data-comment-count]');
    const pillCommentCount   = this.pill.querySelector('[data-pill-comment-count]');
    if (staticCommentCount && pillCommentCount) {
      pillCommentCount.textContent = staticCommentCount.textContent;
    }
  },
};

