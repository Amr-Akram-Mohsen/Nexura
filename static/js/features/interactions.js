/**
 * Nexura — Interactions & Auth Popover Feature (features/interactions.js)
 * Manages optimistic likes, bookmarks, reactions, live counter synchronization,
 * and the anchored contextual micro-prompt (auth popover) for unauthenticated users.
 */
'use strict';

(function () {
  window.Nexura = window.Nexura || {};

  let activeAuthPopover = null;

  function notify(msg, type = 'info') {
    if (window.Nexura.toast) {
      window.Nexura.toast(msg, type);
    } else if (window.Toast && typeof window.Toast.show === 'function') {
      window.Toast.show(msg, type);
    }
  }

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
    let left = btnRect.left + btnRect.width / 2;
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
    if (!btn) return;
    btn.disabled = true;

    try {
      const params = new URLSearchParams({
        action,
        content_id: targetId,
        target_id: targetId,
        target_type: targetType,
      });

      let data;
      if (window.Nexura.http && typeof window.Nexura.http.post === 'function') {
        try {
          data = await window.Nexura.http.post('/handle-interaction', params);
        } catch (err) {
          if (err && err.status === 401) {
            showAuthPopover(btn, action);
            return;
          }
          throw err;
        }
      } else {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
        const res = await fetch('/handle-interaction', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken,
          },
          body: params,
        });

        if (res.status === 401) {
          showAuthPopover(btn, action);
          return;
        }
        data = await res.json();
      }

      if (data.success) {
        if (targetType === 'comment') {
          const commentCard = btn.closest('.comment-card');
          if (commentCard) {
            const likeBtn = commentCard.querySelector(
              '.comment-action-btn[data-interaction="like"]'
            );
            const dislikeBtn = commentCard.querySelector(
              '.comment-action-btn[data-interaction="dislike"]'
            );

            const isLiked =
              data.liked !== undefined ? data.liked : action === 'like' && data.toggled;
            const isDisliked =
              data.disliked !== undefined ? data.disliked : action === 'dislike' && data.toggled;

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
              if (countEl && data.dislike_count !== undefined)
                countEl.textContent = data.dislike_count;
            }
          }
        } else {
          const bar =
            btn.closest('.interaction-bar') ||
            document.querySelector(`.interaction-bar[data-content-id="${targetId}"]`);

          if (action === 'like' || action === 'dislike') {
            const likeBtn = bar
              ? bar.querySelector('[data-interaction="like"]')
              : action === 'like'
                ? btn
                : null;
            const dislikeBtn = bar
              ? bar.querySelector('[data-interaction="dislike"]')
              : action === 'dislike'
                ? btn
                : null;

            const isLiked =
              data.liked !== undefined ? data.liked : action === 'like' && data.toggled;
            const isDisliked =
              data.disliked !== undefined ? data.disliked : action === 'dislike' && data.toggled;

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
              const textNode = Array.from(btn.childNodes).find(
                (n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim()
              );
              if (textNode) {
                textNode.textContent = isSaved ? ' Saved' : ' Save';
              }
            }
          }
        }
      } else {
        notify(data.message || 'Something went wrong.', 'error');
      }
    } catch (err) {
      notify('Could not complete action. Try again.', 'error');
    } finally {
      btn.disabled = false;
    }
  }

  // Delegated click listener for reaction buttons
  document.addEventListener('click', (e) => {
    const interactionBtn = e.target.closest('[data-interaction]');
    if (interactionBtn) {
      e.preventDefault();
      if (interactionBtn.disabled) return;
      const action = interactionBtn.dataset.interaction;
      const targetType = interactionBtn.dataset.targetType || 'content';
      const targetId = interactionBtn.dataset.targetId || interactionBtn.dataset.contentId;
      if (targetId) {
        handleInteraction(action, targetId, interactionBtn, targetType);
      }
    }
  });

  window.Nexura.interactions = {
    handle: handleInteraction,
    showAuthPopover,
  };
})();
