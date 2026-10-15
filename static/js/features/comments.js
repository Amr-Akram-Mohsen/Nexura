/**
 * Nexura — Comment System Feature (features/comments.js)
 * Manages comment submission, nested reply forms, thread expansion/collapse,
 * character counters, auto-grow textareas, and pagination.
 */
'use strict';

(function () {
  window.Nexura = window.Nexura || {};

  function escapeHtml(str) {
    if (window.Nexura.dom && typeof window.Nexura.dom.escapeHtml === 'function') {
      return window.Nexura.dom.escapeHtml(str);
    }
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function notify(msg, type = 'info') {
    if (window.Nexura.toast) {
      window.Nexura.toast(msg, type);
    } else if (window.Toast && typeof window.Toast.show === 'function') {
      window.Toast.show(msg, type);
    }
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

    document.querySelectorAll('.comment-reply-form').forEach((f) => f.remove());

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
      notify('Comment must be at least 2 characters.', 'error');
      if (textarea) textarea.focus();
      return;
    }

    const contentId =
      form.dataset.contentId || form.querySelector('input[name="content_id"]')?.value;
    const parentIdInput = form.querySelector('input[name="parent_id"]');
    const parentId = parentIdInput ? parentIdInput.value : null;

    if (!contentId) {
      notify('Missing content ID.', 'error');
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

      let data;
      if (window.Nexura.http && typeof window.Nexura.http.post === 'function') {
        data = await window.Nexura.http.post('/comments/submit', params);
      } else {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
        const res = await fetch('/comments/submit', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken,
          },
          body: params,
        });
        if (res.status === 401) {
          notify('Please log in to post a comment.', 'info');
          return;
        }
        data = await res.json();
      }

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
              ${
                !parentId
                  ? `
              <div class="comment-reply-slot" id="reply-slot-${c.id}"></div>
              <div class="comment-card__replies" id="replies-${c.id}" style="display:none;"></div>
              `
                  : ''
              }
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
          const existingToggle = parentCard
            ? parentCard.querySelector(
                '.comment-replies-toggle[data-target="replies-' + parentId + '"]'
              )
            : null;
          if (existingToggle) {
            existingToggle.setAttribute('aria-expanded', 'true');
            const countEl = existingToggle.querySelector('span');
            if (countEl) {
              const currentCount = parseInt(countEl.textContent, 10) || 0;
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
          document.querySelectorAll('[data-comment-count]').forEach((el) => {
            el.textContent = data.comment_count;
          });
        }
      } else {
        notify(data.message || 'Could not post comment.', 'error');
      }
    } catch (err) {
      if (err && err.status === 401) {
        notify('Please log in to post a comment.', 'info');
      } else {
        notify('Network error. Could not post comment.', 'error');
      }
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnHtml;
      }
    }
  }

  function initCommentExpands() {
    document.querySelectorAll('.comment-card__expand-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const text = btn.previousElementSibling;
        if (!text) return;
        const isClamped = text.classList.toggle('comment-card__text--clamped');
        btn.textContent = isClamped ? 'Show more' : 'Show less';
        btn.setAttribute('aria-expanded', isClamped ? 'false' : 'true');
      });
    });
  }

  // Delegated event handling for comments
  document.addEventListener('click', (e) => {
    const target = e.target;

    const scrollCommentsBtn = target.closest(
      '[data-action="scroll-to-comments"], a[href="#comments"]'
    );
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
      toShow.forEach((item) => item.classList.remove('comment-list__item--hidden'));
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

    const growable = e.target.closest('.comment-form__input');
    if (growable) {
      const MAX_H = 105;
      growable.style.height = 'auto';
      const next = Math.min(growable.scrollHeight, MAX_H);
      growable.style.height = next + 'px';
      growable.style.overflowY = growable.scrollHeight > MAX_H ? 'auto' : 'hidden';
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    initCommentExpands();
  });

  window.Nexura.comments = {
    handleCommentSubmit,
    toggleReplyForm,
    initCommentExpands,
  };
})();
