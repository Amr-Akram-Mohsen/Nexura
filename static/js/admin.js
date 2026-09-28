/** Admin control plane client interactions and batch operations. */
(function () {
  'use strict';

  function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  function showAdminToast(message, type = 'info') {
    if (window.Nexura && window.Nexura.toast) {
      window.Nexura.toast(message, type);
    } else {
      const toast = document.createElement('div');
      toast.className = `badge badge--${type === 'success' ? 'ready' : type === 'error' ? 'not-ready' : 'almost'}`;
      toast.style.cssText = 'position:fixed;top:20px;right:20px;z-index:9999;padding:12px 20px;box-shadow:0 8px 24px rgba(0,0,0,0.3);font-size:14px;border-radius:10px;animation:fadeIn 0.2s ease;';
      toast.textContent = message;
      document.body.appendChild(toast);
      setTimeout(() => toast.remove(), 3000);
    }
  }
  window.showAdminToast = showAdminToast;

  const sidebar = document.querySelector('.admin-sidebar');
  const hamburgerBtn = document.querySelector('.admin-hamburger');

  if (hamburgerBtn && sidebar) {
    hamburgerBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      sidebar.classList.toggle('open');
    });

    document.addEventListener('click', (e) => {
      if (sidebar.classList.contains('open') && !sidebar.contains(e.target) && !hamburgerBtn.contains(e.target)) {
        sidebar.classList.remove('open');
      }
    });
  }

  const selectAllCheckbox = document.getElementById('select-all-rows');
  const rowCheckboxes = document.querySelectorAll('.row-select-checkbox');
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

  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener('change', function () {
      rowCheckboxes.forEach((cb) => {
        cb.checked = selectAllCheckbox.checked;
      });
      updateBatchBar();
    });
  }

  rowCheckboxes.forEach((cb) => {
    cb.addEventListener('change', updateBatchBar);
  });

  document.querySelectorAll('[data-batch-action]').forEach((btn) => {
    btn.addEventListener('click', async function () {
      const action = this.dataset.batchAction;
      const selected = Array.from(document.querySelectorAll('.row-select-checkbox:checked')).map(
        (cb) => cb.value
      );

      if (!selected.length) {
        showAdminToast('No items selected', 'warning');
        return;
      }

      if (action === 'delete' && !confirm(`Are you sure you want to delete ${selected.length} item(s)?`)) {
        return;
      }

      try {
        const formData = new FormData();
        formData.append('action', action);
        formData.append('csrf_token', getCsrfToken());
        selected.forEach((id) => formData.append('content_ids', id));

        const res = await fetch('/admin/contents/batch', {
          method: 'POST',
          body: formData,
          headers: { 'X-CSRFToken': getCsrfToken() },
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
    });
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
          if (taskProgressPanel) taskProgressPanel.style.display = 'block';
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
            taskProgressBar.style.width = `${task.progress || 10}%`;
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
          taskProgressBar.style.width = `${task.progress || 10}%`;
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

  document.querySelectorAll('[data-merge-entity-btn]').forEach((btn) => {
    btn.addEventListener('click', async function () {
      const sourceId = this.dataset.sourceId;
      const targetId = this.dataset.targetId;
      const sourceName = this.dataset.sourceName;
      const targetName = this.dataset.targetName;

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
    });
  });

  document.querySelectorAll('[data-moderate-comment]').forEach((btn) => {
    btn.addEventListener('click', async function () {
      const commentId = this.dataset.commentId;
      const action = this.dataset.moderateComment;

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
    });
  });

  window.copyToClipboard = function (text, btnElement) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        showAdminToast('Copied to clipboard! ✓', 'success');
        if (btnElement) {
          const original = btnElement.innerHTML;
          btnElement.innerHTML = '✓ Copied';
          btnElement.style.color = 'var(--accent-green)';
          setTimeout(() => {
            btnElement.innerHTML = original;
            btnElement.style.color = '';
          }, 2000);
        }
      }).catch(() => {
        showAdminToast('Failed to copy', 'error');
      });
    }
  };
})();
