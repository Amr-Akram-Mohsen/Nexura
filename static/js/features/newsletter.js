/**
 * Nexura — Newsletter System & Cross-Tab Sync (features/newsletter.js)
 * Manages newsletter subscription, unsubscription, feedback toasts,
 * and real-time UI synchronization across open browser tabs via BroadcastChannel & localStorage.
 */
'use strict';

(function () {
  window.Nexura = window.Nexura || {};

  const newsletterChannel =
    typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('nexura_newsletter_sync') : null;

  function notify(msg, type = 'info') {
    if (window.Nexura && typeof window.Nexura.toast === 'function') {
      window.Nexura.toast(msg, type);
    } else if (window.Toast && typeof window.Toast.show === 'function') {
      window.Toast.show(msg, type);
    }
  }

  function broadcastNewsletterState(isSubscribed, email) {
    if (newsletterChannel) {
      try {
        newsletterChannel.postMessage({ type: 'newsletter_state_changed', isSubscribed, email });
      } catch (_) {}
    }
    try {
      localStorage.setItem(
        'nexura_newsletter_sync',
        JSON.stringify({ isSubscribed, email, time: Date.now() })
      );
    } catch (_) {}
  }

  function syncNewsletterBoxesAcrossUI(isSubscribed, email) {
    document.querySelectorAll('[data-newsletter-box]').forEach((box) => {
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
      } catch (_) {}
    }
  });

  async function handleSubscribe(form, btn) {
    const input = form.querySelector('input[name="email"], input[type="email"]');
    const email = input ? input.value.trim() : '';
    if (!email || !email.includes('@')) {
      notify('Please enter a valid email address.', 'error');
      return;
    }

    const triggerBtn =
      btn || form.querySelector('[data-action="subscribe"], button[type="submit"]');
    const originalText = triggerBtn ? triggerBtn.textContent : '';
    if (triggerBtn) {
      triggerBtn.disabled = true;
      const spinner = document.createElement('span');
      spinner.className = 'spinner';
      triggerBtn.replaceChildren(spinner);
    }

    try {
      const params = new URLSearchParams({ email });
      let data;
      if (window.Nexura.http && typeof window.Nexura.http.post === 'function') {
        data = await window.Nexura.http.post('/subscribe', params);
      } else {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
        const res = await fetch('/subscribe', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken,
          },
          body: params,
        });
        data = await res.json();
      }

      if (data.success) {
        notify(data.message || 'Thank you! Please check your inbox to confirm.', 'success');
        if (data.is_confirmed || data.already_subscribed) {
          syncNewsletterBoxesAcrossUI(true, data.email || email);
          broadcastNewsletterState(true, data.email || email);
        }
        form.reset();
      } else {
        notify(data.message || 'Subscription failed. Try again.', 'error');
      }
    } catch (_) {
      notify('Network error. Please try again.', 'error');
    } finally {
      if (triggerBtn) {
        triggerBtn.disabled = false;
        triggerBtn.textContent = originalText;
      }
    }
  }

  async function handleUnsubscribe(btn) {
    const box = btn.closest('[data-newsletter-box]');
    const emailEl = box ? box.querySelector('[data-newsletter-email]') : null;
    const email = emailEl ? emailEl.textContent.trim() : '';

    const originalText = btn.textContent;
    btn.disabled = true;
    const spinner = document.createElement('span');
    spinner.className = 'spinner';
    btn.replaceChildren(spinner);

    try {
      const params = new URLSearchParams({ email });
      let data;
      if (window.Nexura.http && typeof window.Nexura.http.post === 'function') {
        data = await window.Nexura.http.post('/unsubscribe', params);
      } else {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
        const res = await fetch('/unsubscribe', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken,
          },
          body: params,
        });
        data = await res.json();
      }

      if (data.success) {
        notify(data.message || 'You have been unsubscribed.', 'success');
        syncNewsletterBoxesAcrossUI(false, email);
        broadcastNewsletterState(false, email);
      } else {
        notify(data.message || 'Could not unsubscribe. Please try again.', 'error');
      }
    } catch (_) {
      notify('Network error. Please try again.', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = originalText;
    }
  }

  // Delegated event handling for newsletter
  document.addEventListener('click', (e) => {
    const target = e.target;
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
  });

  document.addEventListener('submit', async (e) => {
    const subForm = e.target.closest('form[data-subscribe-form]');
    if (subForm) {
      e.preventDefault();
      const btn = subForm.querySelector('[data-action="subscribe"], button[type="submit"]');
      await handleSubscribe(subForm, btn);
    }
  });

  window.Nexura.newsletter = {
    handleSubscribe,
    handleUnsubscribe,
    syncNewsletterBoxesAcrossUI,
    broadcastNewsletterState,
  };
})();
