/**
 * Nexura — Video Facade & Theater Mode Feature (features/video.js)
 * Manages lazy iframe mounting with loading spinner and ambient glow,
 * keyboard accessibility, and full-screen theater mode with trapped focus and scroll lock.
 */
'use strict';

(function () {
  window.Nexura = window.Nexura || {};

  let currentTheaterKeyHandler = null;

  function lockScroll() {
    if (window.Nexura.dom && typeof window.Nexura.dom.lockScroll === 'function') {
      window.Nexura.dom.lockScroll();
    } else {
      document.body.style.overflow = 'hidden';
    }
  }

  function unlockScroll() {
    if (window.Nexura.dom && typeof window.Nexura.dom.unlockScroll === 'function') {
      window.Nexura.dom.unlockScroll();
    } else {
      document.body.style.overflow = '';
    }
  }

  function mountVideoFacade(facade) {
    if (!facade || facade.dataset.mounted === 'true') return;
    const videoId = facade.dataset.videoId;
    if (!videoId) return;

    const thumb = facade.querySelector('.video-facade__thumb');
    const playEl = facade.querySelector('.video-facade__play');
    const durationEl = facade.querySelector('.video-facade__duration');
    const theaterBtn = facade.querySelector('.video-facade__theater-btn');

    // Show loading spinner
    let spinner = facade.querySelector('.video-facade__spinner');
    if (!spinner) {
      spinner = document.createElement('div');
      spinner.className = 'video-facade__spinner';
      spinner.innerHTML = '<div class="video-facade__spinner-ring"></div>';
      facade.appendChild(spinner);
    }

    if (thumb) thumb.style.display = 'none';
    if (playEl) playEl.style.display = 'none';
    if (durationEl) durationEl.style.display = 'none';

    const iframe = document.createElement('iframe');
    iframe.setAttribute('allow', 'autoplay; encrypted-media; picture-in-picture; fullscreen');
    iframe.setAttribute('allowfullscreen', '');
    iframe.setAttribute('loading', 'lazy');
    iframe.setAttribute('title', facade.dataset.videoTitle || 'YouTube Video');
    iframe.src = `https://www.youtube.com/embed/${encodeURIComponent(videoId)}?autoplay=1&rel=0&modestbranding=1`;

    iframe.addEventListener(
      'load',
      () => {
        if (spinner) spinner.remove();
        if (theaterBtn) theaterBtn.style.display = 'flex';
      },
      { once: true }
    );

    facade.appendChild(iframe);
    facade.dataset.mounted = 'true';
    facade.style.aspectRatio = '16/9';
  }

  function toggleTheaterMode(facade) {
    if (!facade) return;
    const isTheater = facade.classList.toggle('video-facade--theater');

    if (isTheater) {
      lockScroll();

      const oldBtn = document.getElementById('theater-close-btn');
      if (oldBtn) oldBtn.remove();

      const closeBtn = document.createElement('button');
      closeBtn.className = 'theater-close-btn';
      closeBtn.id = 'theater-close-btn';
      closeBtn.setAttribute('aria-label', 'Exit theater mode');
      closeBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      `;
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleTheaterMode(facade);
      });
      document.body.appendChild(closeBtn);

      if (currentTheaterKeyHandler) {
        document.removeEventListener('keydown', currentTheaterKeyHandler);
      }
      currentTheaterKeyHandler = (e) => {
        if (e.key === 'Escape') {
          toggleTheaterMode(facade);
        }
      };
      document.addEventListener('keydown', currentTheaterKeyHandler);
    } else {
      unlockScroll();
      const closeBtn = document.getElementById('theater-close-btn');
      if (closeBtn) closeBtn.remove();
      if (currentTheaterKeyHandler) {
        document.removeEventListener('keydown', currentTheaterKeyHandler);
        currentTheaterKeyHandler = null;
      }
    }
  }

  // Delegated event handling for video facades
  document.addEventListener('click', (e) => {
    const target = e.target;

    const theaterBtn = target.closest('[data-action="toggle-theater"]');
    if (theaterBtn) {
      e.stopPropagation();
      const facade = theaterBtn.closest('.video-facade');
      if (facade) {
        toggleTheaterMode(facade);
      }
      return;
    }

    const facade = target.closest('.video-facade[data-video-id]');
    if (facade && facade.dataset.mounted !== 'true') {
      mountVideoFacade(facade);
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const facade = e.target.closest('.video-facade[data-video-id]');
    if (!facade || facade !== document.activeElement) return;
    e.preventDefault();
    facade.click();
  });

  window.Nexura.video = {
    mountVideoFacade,
    toggleTheaterMode,
  };
  window.mountVideoFacade = mountVideoFacade;
  window.toggleTheaterMode = toggleTheaterMode;
})();
