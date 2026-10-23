/** Admin control plane client interactions and batch operations. */
(function () {
  'use strict';

  function getCsrfToken() {
    if (window.Nexura && window.Nexura.http && typeof window.Nexura.http.getCsrfToken === 'function') {
      return window.Nexura.http.getCsrfToken();
    }
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  function showAdminToast(message, type = 'info') {
    if (window.Nexura && window.Nexura.toast) {
      window.Nexura.toast(message, type);
    } else {
      const toast = document.createElement('div');
      toast.className = `admin-toast-fallback badge badge--${type === 'success' ? 'ready' : type === 'error' ? 'not-ready' : 'almost'}`;
      toast.textContent = message;
      document.body.appendChild(toast);
      setTimeout(() => toast.remove(), 3000);
    }
  }
  window.showAdminToast = showAdminToast;
  window.Nexura = window.Nexura || {};
  window.Nexura.showAdminToast = showAdminToast;

  const sidebar = document.querySelector('.admin-sidebar');
  const hamburgerBtn = document.querySelector('.admin-hamburger');

  if (hamburgerBtn && sidebar) {
    hamburgerBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      sidebar.classList.toggle('open');
    });

    document.addEventListener('click', (e) => {
      if (
        sidebar.classList.contains('open') &&
        !sidebar.contains(e.target) &&
        !hamburgerBtn.contains(e.target)
      ) {
        sidebar.classList.remove('open');
      }
    });
  }

  const batchBar = document.getElementById('batch-action-bar');
  const selectedCountEl = document.getElementById('selected-count-label');

  function updateBatchBar() {
    const selected = document.querySelectorAll('.row-select-checkbox:checked');
    if (selectedCountEl) {
      selectedCountEl.textContent = `${selected.length} selected`;
    }
    if (batchBar) {
      if (selected.length > 0) {
        batchBar.classList.add('show');
      } else {
        batchBar.classList.remove('show');
      }
    }
  }

  // Delegated table selection listener
  document.addEventListener('change', (e) => {
    if (e.target.id === 'select-all-rows') {
      const isChecked = e.target.checked;
      document.querySelectorAll('.row-select-checkbox').forEach((cb) => {
        cb.checked = isChecked;
      });
      updateBatchBar();
    } else if (e.target.matches('.row-select-checkbox')) {
      updateBatchBar();
    }
  });

  const runIngestionForm = document.getElementById('run-ingestion-form');
  const taskProgressPanel = document.getElementById('task-progress-panel');
  const taskProgressBar = document.getElementById('task-progress-bar');
  const taskStatusLabel = document.getElementById('task-status-label');

  if (runIngestionForm) {
    runIngestionForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      const formData = new FormData(this);
      const submitBtn = this.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;

      try {
        const res = await fetch('/admin/ingestions/run', {
          method: 'POST',
          body: formData,
          headers: { 'X-CSRFToken': getCsrfToken() },
        });
        const data = await res.json();

        if (data.success && data.task_id) {
          showAdminToast('Task started...', 'info');
          if (taskProgressPanel) taskProgressPanel.classList.add('is-visible');
          pollTaskStatus(data.task_id);
        } else {
          showAdminToast(data.message || 'Failed to start task', 'error');
          if (submitBtn) submitBtn.disabled = false;
        }
      } catch (err) {
        showAdminToast('Failed to contact server', 'error');
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }

  function pollTaskStatus(taskId) {
    if (typeof EventSource !== 'undefined') {
      const source = new EventSource(`/admin/ingestions/api/task/${taskId}/stream`);

      source.onmessage = function (event) {
        try {
          const task = JSON.parse(event.data);
          if (task.error) {
            source.close();
            showAdminToast(`Task error: ${task.error}`, 'error');
            return;
          }

          if (taskProgressBar) {
            taskProgressBar.style.setProperty('--progress', `${task.progress || 10}%`);
          }
          if (taskStatusLabel) {
            taskStatusLabel.textContent = `${(task.status || '').toUpperCase()} (${task.progress}%): ${task.message || ''}`;
          }

          if (task.status === 'completed' || task.status === 'complete') {
            source.close();
            showAdminToast('Ingestion completed successfully!', 'success');
            setTimeout(() => window.location.reload(), 1200);
          } else if (task.status === 'failed') {
            source.close();
            showAdminToast(`Task failed: ${task.error || 'Unknown error'}`, 'error');
          }
        } catch (e) {
          // Keep stream listening
        }
      };

      source.onerror = function () {
        source.close();
        pollTaskStatusFallback(taskId);
      };
      return;
    }

    pollTaskStatusFallback(taskId);
  }

  function pollTaskStatusFallback(taskId) {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/admin/ingestions/api/task/${taskId}`);
        if (!res.ok) {
          clearInterval(interval);
          return;
        }
        const task = await res.json();

        if (taskProgressBar) {
          taskProgressBar.style.setProperty('--progress', `${task.progress || 10}%`);
        }
        if (taskStatusLabel) {
          taskStatusLabel.textContent = `${task.status.toUpperCase()} (${task.progress}%): ${task.message || ''}`;
        }

        if (task.status === 'completed' || task.status === 'complete') {
          clearInterval(interval);
          showAdminToast('Ingestion completed successfully!', 'success');
          setTimeout(() => window.location.reload(), 1200);
        } else if (task.status === 'failed') {
          clearInterval(interval);
          showAdminToast(`Task failed: ${task.error || 'Unknown error'}`, 'error');
        }
      } catch (e) {
        clearInterval(interval);
      }
    }, 1500);
  }

  window.copyToClipboard = function (text, btnElement) {
    if (navigator.clipboard) {
      navigator.clipboard
        .writeText(text)
        .then(() => {
          showAdminToast('Copied to clipboard! ✓', 'success');
          if (btnElement) {
            const original = btnElement.textContent;
            btnElement.textContent = '✓ Copied';
            btnElement.classList.add('btn--copied');
            setTimeout(() => {
              btnElement.textContent = original;
              btnElement.classList.remove('btn--copied');
            }, 2000);
          }
        })
        .catch(() => {
          showAdminToast('Failed to copy', 'error');
        });
    }
  };

  /* Delegated click handler for admin actions (copy draft, batch operations, taxonomy merge, moderation) */
  document.addEventListener('click', async function (e) {
    // 1. Copy draft snippet
    const copyBtn = e.target.closest('[data-action="copy-draft"]');
    if (copyBtn) {
      const card = copyBtn.closest('.social-card');
      const copyBox = card ? card.querySelector('.social-copy-box') : null;
      const text = copyBox ? copyBox.textContent.trim() : '';
      if (text) {
        window.copyToClipboard(text, copyBtn);
      }
      return;
    }

    // 2. Batch actions (contents table)
    const batchBtn = e.target.closest('[data-batch-action]');
    if (batchBtn) {
      const action = batchBtn.dataset.batchAction;
      const selected = Array.from(document.querySelectorAll('.row-select-checkbox:checked'))
        .map((cb) => parseInt(cb.value, 10))
        .filter(Boolean);

      if (!selected.length) {
        showAdminToast('No items selected', 'error');
        return;
      }

      if (action === 'delete' && !confirm(`Permanently delete ${selected.length} item(s)?`)) {
        return;
      }

      try {
        const res = await fetch('/admin/contents/batch', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({ action, content_ids: selected }),
        });
        const data = await res.json();
        if (data.success) {
          showAdminToast(data.message, 'success');
          setTimeout(() => window.location.reload(), 800);
        } else {
          showAdminToast(data.message || 'Batch action failed', 'error');
        }
      } catch (err) {
        showAdminToast('Network error during batch action', 'error');
      }
      return;
    }

    // 3. Taxonomy merge entity
    const mergeBtn = e.target.closest('[data-merge-entity-btn]');
    if (mergeBtn) {
      const sourceId = mergeBtn.dataset.sourceId;
      const targetId = mergeBtn.dataset.targetId;
      const sourceName = mergeBtn.dataset.sourceName;
      const targetName = mergeBtn.dataset.targetName;

      if (!confirm(`Merge "${sourceName}" into "${targetName}"? "${sourceName}" will be deleted.`)) {
        return;
      }

      try {
        const formData = new FormData();
        formData.append('source_id', sourceId);
        formData.append('target_id', targetId);
        formData.append('csrf_token', getCsrfToken());

        const res = await fetch('/admin/taxonomy/merge', {
          method: 'POST',
          body: formData,
          headers: { 'X-CSRFToken': getCsrfToken() },
        });
        const data = await res.json();

        if (data.success) {
          showAdminToast(data.message, 'success');
          setTimeout(() => window.location.reload(), 800);
        } else {
          showAdminToast(data.message || 'Merge failed', 'error');
        }
      } catch (err) {
        showAdminToast('Network error during merge', 'error');
      }
      return;
    }

    // 4. Moderate comment
    const modBtn = e.target.closest('[data-moderate-comment]');
    if (modBtn) {
      const commentId = modBtn.dataset.commentId;
      const action = modBtn.dataset.moderateComment;

      try {
        const formData = new FormData();
        formData.append('csrf_token', getCsrfToken());

        const res = await fetch(`/admin/moderation/comments/${commentId}/${action}`, {
          method: 'POST',
          body: formData,
          headers: { 'X-CSRFToken': getCsrfToken() },
        });
        const data = await res.json();

        if (data.success) {
          showAdminToast(data.message, 'success');
          const row = document.getElementById(`comment-row-${commentId}`);
          if (action === 'hard_delete' && row) {
            row.remove();
          } else {
            setTimeout(() => window.location.reload(), 600);
          }
        } else {
          showAdminToast(data.message || 'Action failed', 'error');
        }
      } catch (err) {
        showAdminToast('Network error', 'error');
      }
      return;
    }
  });
})();
