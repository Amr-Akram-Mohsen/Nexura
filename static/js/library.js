/**
 * Nexura Library Interactions (library.js)
 * Optimistic removal of reading history and saved bookmarks,
 * animated card dismissal, live count updates, and accessible confirmation modal.
 */
'use strict';

(function () {
  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    const input = document.querySelector('input[name="csrf_token"]');
    return input ? input.value : '';
  }

  function notify(msg, type = 'info') {
    if (window.Toast && typeof window.Toast.show === 'function') {
      window.Toast.show(msg, type);
    }
  }

  function updateCount(type, deltaOrExact) {
    const headerEl = document.querySelector(`[data-library-count="${type}"]`);
    const tabEl = document.querySelector(`[data-tab-count="${type}"]`);

    let newCount = 0;
    if (typeof deltaOrExact === 'number' && deltaOrExact < 0) {
      const current = parseInt(tabEl?.textContent || headerEl?.textContent || '0', 10);
      newCount = Math.max(0, current + deltaOrExact);
    } else {
      newCount = Math.max(0, parseInt(deltaOrExact, 10) || 0);
    }

    if (headerEl) headerEl.textContent = newCount;
    if (tabEl) tabEl.textContent = newCount;
    return newCount;
  }

  function showEmptyState() {
    const emptyState = document.getElementById('library-empty-state');
    if (emptyState) {
      emptyState.style.display = 'flex';
      emptyState.removeAttribute('hidden');
    }
    const pagination = document.getElementById('library-pagination');
    if (pagination) {
      pagination.style.display = 'none';
    }
    const clearActions = document.getElementById('clear-history-actions');
    if (clearActions) {
      clearActions.style.display = 'none';
    }
  }

  /* ─── Clear History Modal Controller ─────────────────────── */
  const ClearHistoryModal = {
    modal: null,
    prevFocus: null,

    init() {
      this.modal = document.getElementById('clear-history-modal');
      if (!this.modal) return;

      // Open trigger
      document.addEventListener('click', (e) => {
        const openBtn = e.target.closest('[data-action="open-clear-modal"]');
        if (openBtn) {
          e.preventDefault();
          this.open(openBtn);
          return;
        }

        // Close triggers
        const closeBtn = e.target.closest('[data-action="close-clear-modal"]');
        if (closeBtn) {
          e.preventDefault();
          this.close();
          return;
        }

        // Backdrop click to dismiss
        if (e.target === this.modal) {
          this.close();
          return;
        }
      });

      // Escape key to dismiss
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.modal.classList.contains('is-open')) {
          this.close();
        }
      });

      // Form submission
      const form = document.getElementById('clear-history-form');
      if (form) {
        form.addEventListener('submit', (e) => this.handleClearSubmit(e, form));
      }
    },

    open(triggerEl) {
      if (!this.modal) return;
      this.prevFocus = triggerEl || document.activeElement;
      this.modal.classList.add('is-open');
      document.body.style.overflow = 'hidden';

      // Focus Cancel button
      const cancelBtn = this.modal.querySelector('[data-action="close-clear-modal"]');
      if (cancelBtn) cancelBtn.focus();
    },

    close() {
      if (!this.modal) return;
      this.modal.classList.remove('is-open');
      document.body.style.overflow = '';
      if (this.prevFocus && typeof this.prevFocus.focus === 'function') {
        this.prevFocus.focus();
      }
    },

    async handleClearSubmit(e, form) {
      e.preventDefault();
      const submitBtn = document.getElementById('confirm-clear-btn');
      const originalText = submitBtn ? submitBtn.textContent : 'Clear History';

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Clearing...';
      }

      try {
        const res = await fetch(form.action, {
          method: 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: new URLSearchParams(new FormData(form)),
        });

        const data = await res.json();
        if (data.success) {
          this.close();

          // Animate out all history rows
          const rows = document.querySelectorAll('.history-row');
          rows.forEach((row) => row.classList.add('history-row--removing'));

          setTimeout(() => {
            rows.forEach((row) => row.remove());
            updateCount('history', 0);
            showEmptyState();
            notify('Reading history cleared.', 'success');
          }, 320);
        } else {
          notify(data.message || 'Could not clear history.', 'error');
        }
      } catch (err) {
        notify('Network error. Could not clear history.', 'error');
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = originalText;
        }
      }
    },
  };

  /* ─── Row & Card Removal Interactions ───────────────────── */
  function initLibraryInteractions() {
    document.addEventListener('click', async (e) => {
      // 1. Remove single item from reading history
      const historyRemoveBtn = e.target.closest('[data-action="remove-history"]');
      if (historyRemoveBtn) {
        e.preventDefault();
        e.stopPropagation();
        if (historyRemoveBtn.disabled) return;

        const contentId = historyRemoveBtn.dataset.contentId;
        const row = document.getElementById(`history-row-${contentId}`) || historyRemoveBtn.closest('.history-row');
        if (!row || !contentId) return;

        historyRemoveBtn.disabled = true;

        // Optimistically animate row out
        row.classList.add('history-row--removing');

        try {
          const res = await fetch(`/library/history/remove/${encodeURIComponent(contentId)}`, {
            method: 'POST',
            headers: {
              'X-Requested-With': 'XMLHttpRequest',
              'X-CSRFToken': getCsrfToken(),
            },
          });

          const data = await res.json();
          if (data.success) {
            setTimeout(() => {
              row.remove();
              const remaining = updateCount('history', -1);
              if (remaining <= 0 || document.querySelectorAll('.history-row').length === 0) {
                showEmptyState();
              }
              notify('Removed from history.', 'info');
            }, 300);
          } else {
            // Revert animation on failure
            row.classList.remove('history-row--removing');
            historyRemoveBtn.disabled = false;
            notify(data.message || 'Could not remove item.', 'error');
          }
        } catch (err) {
          row.classList.remove('history-row--removing');
          historyRemoveBtn.disabled = false;
          notify('Network error. Could not remove item.', 'error');
        }
        return;
      }

      // 2. Unsave bookmark card from saved items
      const unsaveBtn = e.target.closest('[data-action="unsave"]');
      if (unsaveBtn) {
        e.preventDefault();
        e.stopPropagation();
        if (unsaveBtn.disabled) return;

        const contentId = unsaveBtn.dataset.contentId;
        const card = document.getElementById(`saved-card-${contentId}`) || unsaveBtn.closest('.saved-card');
        if (!card || !contentId) return;

        unsaveBtn.disabled = true;

        // Optimistically animate card out
        card.classList.add('saved-card--removing');

        try {
          const res = await fetch('/handle-interaction', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
              'X-Requested-With': 'XMLHttpRequest',
              'X-CSRFToken': getCsrfToken(),
            },
            body: new URLSearchParams({
              action: 'save',
              content_id: contentId,
              target_id: contentId,
              target_type: 'content',
            }),
          });

          const data = await res.json();
          if (data.success) {
            setTimeout(() => {
              card.remove();
              const remaining = updateCount('saved', -1);
              if (remaining <= 0 || document.querySelectorAll('.saved-card').length === 0) {
                showEmptyState();
              }
              notify('Item removed from saved.', 'info');
            }, 300);
          } else {
            // Revert animation on failure
            card.classList.remove('saved-card--removing');
            unsaveBtn.disabled = false;
            notify(data.message || 'Could not remove bookmark.', 'error');
          }
        } catch (err) {
          card.classList.remove('saved-card--removing');
          unsaveBtn.disabled = false;
          notify('Network error. Could not remove bookmark.', 'error');
        }
        return;
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    ClearHistoryModal.init();
    initLibraryInteractions();
  });
})();
