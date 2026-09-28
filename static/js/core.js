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

  show(message, type = 'info', duration = 3500) {
    const c = this._getContainer();
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.setAttribute('role', 'alert');

    const icons = {
      success: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`,
      error: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
      info: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    };

    toast.innerHTML = `${icons[type] || icons.info}<span>${message}</span>`;
    c.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('toast--exit');
      toast.addEventListener('animationend', () => toast.remove(), { once: true });
    }, duration);
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

  const cancelReplyBtn = target.closest('[data-action="cancel-reply"]');
  if (cancelReplyBtn) {
    e.preventDefault();
    const replyForm = cancelReplyBtn.closest('.comment-reply-form');
    if (replyForm) replyForm.remove();
    return;
  }
});

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
      Toast.show('Please log in to interact.', 'info');
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
          Toast.show(isSaved ? 'Saved to your library!' : 'Removed from library.', 'success');
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
          parentCard.querySelector('.comment-card__body').appendChild(repliesContainer);
        }
        if (repliesContainer) {
          repliesContainer.style.display = 'flex';
          repliesContainer.insertAdjacentHTML('beforeend', cardHtml);
        }
        form.remove();
      } else {
        const list = document.getElementById('comment-list');
        if (list) {
          list.insertAdjacentHTML('afterbegin', cardHtml);
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

      Toast.show('Comment posted successfully!', 'success');
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
});

document.addEventListener('DOMContentLoaded', () => {
  ThemeManager.init();
  HeroCarousel.init(document.querySelector('.hero-carousel'));
  ProgressiveReveal.init('.grid-cards[data-reveal]', '[data-reveal-trigger]');
  ViewTracker.init();
  initMobileNav();
});
