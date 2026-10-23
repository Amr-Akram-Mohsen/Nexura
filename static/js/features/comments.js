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
    if (window.Nexura && typeof window.Nexura.toast === 'function') {
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

    const template = document.getElementById('comment-reply-form-template');
    if (!template || !template.content) return;
    const clone = template.content.cloneNode(true);
    const form = clone.querySelector('.comment-reply-form');
    if (!form) return;


    form.setAttribute('data-content-id', contentId);
    const contentInput = form.querySelector('input[name="content_id"]');
    if (contentInput) contentInput.value = contentId;
    const parentInput = form.querySelector('input[name="parent_id"]');
    if (parentInput) parentInput.value = parentId;

    slot.appendChild(form);
    const textarea = form.querySelector('textarea');
    if (textarea) textarea.focus();
  }

  function buildCommentCard(c, parentId) {
    const template = document.getElementById('comment-card-template');
    let card;
    if (template && template.content) {
      const clone = template.content.cloneNode(true);
      card = clone.querySelector('.comment-card');
    }
    if (!card) {
      card = document.createElement('div');
      card.className = 'comment-card';
    }

    card.id = `comment-${c.id}`;
    card.dataset.commentId = String(c.id);
    card.dataset.userId = String(c.user_id);
    if (parentId) {
      card.classList.add('comment-card--reply');
    }

    const initial = (c.user_name || 'C')[0].toUpperCase();
    const avatar = card.querySelector('.comment-card__avatar');
    if (avatar) avatar.textContent = initial;

    const author = card.querySelector('.comment-card__author');
    if (author) author.textContent = c.user_name || 'Community Member';

    const date = card.querySelector('.comment-card__date');
    if (date) date.textContent = c.formatted_date || 'Just now';

    const text = card.querySelector('.comment-card__text');
    if (text) text.textContent = c.content || '';

    const actionBtns = card.querySelectorAll('.comment-action-btn');
    actionBtns.forEach((btn) => {
      btn.dataset.targetId = String(c.id);
    });

    const replySlot = card.querySelector('.comment-reply-slot');
    if (replySlot) {
      if (parentId) {
        replySlot.remove();
      } else {
        replySlot.id = `reply-slot-${c.id}`;
      }
    }

    const repliesContainer = card.querySelector('.comment-card__replies');
    if (repliesContainer) {
      if (parentId) {
        repliesContainer.remove();
      } else {
        repliesContainer.id = `replies-${c.id}`;
        repliesContainer.setAttribute('aria-hidden', 'true');
      }
    }

    return card;
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

    let originalBtnChildren = null;
    if (submitBtn) {
      submitBtn.disabled = true;
      originalBtnChildren = Array.from(submitBtn.childNodes).map((n) => n.cloneNode(true));
      const spinner = document.createElement('span');
      spinner.className = 'spinner';
      submitBtn.replaceChildren(spinner);
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
        const newCard = buildCommentCard(c, parentId);

        if (parentId) {
          const parentCard = document.getElementById(`comment-${parentId}`);
          let repliesContainer = document.getElementById(`replies-${parentId}`);
          if (!repliesContainer && parentCard) {
            repliesContainer = document.createElement('div');
            repliesContainer.className = 'comment-card__replies';
            repliesContainer.id = `replies-${parentId}`;
            repliesContainer.setAttribute('aria-hidden', 'false');
            const parentBody = parentCard.querySelector('.comment-card__body');
            if (parentBody) {
              parentBody.appendChild(repliesContainer);
            } else {
              parentCard.appendChild(repliesContainer);
            }
          }
          if (repliesContainer) {
            repliesContainer.setAttribute('aria-hidden', 'false');
            repliesContainer.appendChild(newCard);
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
          } else if (parentCard && repliesContainer) {
            // First reply — create the toggle button before the replies container
            const toggleTemplate = document.getElementById('comment-replies-toggle-template');
            let toggleBtn;
            if (toggleTemplate && toggleTemplate.content) {
              const clone = toggleTemplate.content.cloneNode(true);
              toggleBtn = clone.querySelector('.comment-replies-toggle');
            }
            if (!toggleBtn) {
              toggleBtn = document.createElement('button');
              toggleBtn.className = 'comment-replies-toggle';
              toggleBtn.type = 'button';
              const span = document.createElement('span');
              span.textContent = '1 reply';
              toggleBtn.appendChild(span);
            }
            toggleBtn.dataset.action = 'toggle-replies';
            toggleBtn.dataset.target = `replies-${parentId}`;
            toggleBtn.setAttribute('aria-expanded', 'true');
            repliesContainer.parentNode.insertBefore(toggleBtn, repliesContainer);
          }
          form.remove();
        } else {
          const list = document.getElementById('comment-list');
          if (list) {
            const wrapper = document.createElement('div');
            wrapper.className = 'comment-list__item';
            wrapper.appendChild(newCard);
            list.insertAdjacentElement('afterbegin', wrapper);
          }
          const emptyState = document.getElementById('comments-empty');
          if (emptyState) {
            if (window.Nexura && window.Nexura.dom) window.Nexura.dom.hide(emptyState);
            else emptyState.setAttribute('hidden', '');
          }

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
        if (originalBtnChildren) {
          submitBtn.replaceChildren(...originalBtnChildren);
        }
      }
    }
  }

  function initCommentExpands() {
    // Kept for backward compatibility; expand buttons are now handled via event delegation.
  }

  // Delegated event handling for comments
  document.addEventListener('click', (e) => {
    const target = e.target;

    const expandBtn = target.closest('.comment-card__expand-btn');
    if (expandBtn) {
      e.preventDefault();
      const text = expandBtn.previousElementSibling;
      if (!text) return;
      const isClamped = text.classList.toggle('comment-card__text--clamped');
      expandBtn.textContent = isClamped ? 'Show more' : 'Show less';
      expandBtn.setAttribute('aria-expanded', isClamped ? 'false' : 'true');
      return;
    }

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
        container.setAttribute('aria-hidden', 'true');
        repliesToggle.setAttribute('aria-expanded', 'false');
      } else {
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
        if (loadMoreEl) {
          if (window.Nexura && window.Nexura.dom) window.Nexura.dom.hide(loadMoreEl);
          else loadMoreEl.setAttribute('hidden', '');
        }
      } else {
        const textSpan = loadMoreBtn.querySelector('.comments-load-more__text');
        const textContent = `Show ${remaining} more ${remaining === 1 ? 'comment' : 'comments'}`;
        if (textSpan) {
          textSpan.textContent = textContent;
        } else {
          loadMoreBtn.lastChild.textContent = ` ${textContent}`;
        }
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
