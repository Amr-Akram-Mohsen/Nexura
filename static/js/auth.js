/**
 * Nexura — Authentication Module (auth.js)
 * Client-side auth behavior: password strength metering and validation states.
 */
(function () {
  'use strict';

  function initPasswordStrength() {
    const passwordInput = document.getElementById('password');
    const bar = document.getElementById('pw-strength-bar');
    const label = document.getElementById('pw-strength-label');

    if (!passwordInput || !bar) return;

    passwordInput.addEventListener('input', function () {
      const pw = this.value;
      if (!pw) {
        bar.dataset.score = '0';
        if (label) {
          label.textContent = '';
          label.dataset.score = '';
        }
        return;
      }

      let score = 0;
      if (/[a-z]/.test(pw)) score++;
      if (/[A-Z]/.test(pw)) score++;
      if (/\d/.test(pw)) score++;
      if (/[^A-Za-z0-9]/.test(pw)) score++;

      const isTooShort = pw.length < 8;
      const effectiveScore = isTooShort ? 0 : score;
      bar.dataset.score = String(effectiveScore);

      if (label) {
        const labels = ['', 'Weak', 'Fair', 'Good', 'Strong'];
        label.textContent = isTooShort ? 'Too short' : labels[score] || '';
        label.dataset.score = isTooShort ? 'too-short' : score ? String(score) : '';
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPasswordStrength);
  } else {
    initPasswordStrength();
  }
})();
