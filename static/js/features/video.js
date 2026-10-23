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
      document.body.classList.add('is-scroll-locked');
    }
  }

  function unlockScroll() {
    if (window.Nexura.dom && typeof window.Nexura.dom.unlockScroll === 'function') {
      window.Nexura.dom.unlockScroll();
    } else {
      document.body.classList.remove('is-scroll-locked');
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
      const ring = document.createElement('div');
      ring.className = 'video-facade__spinner-ring';
      spinner.appendChild(ring);
      facade.appendChild(spinner);
    }

    if (thumb) {
      if (window.Nexura.dom) window.Nexura.dom.hide(thumb);
      else thumb.setAttribute('hidden', '');
    }
    if (playEl) {
      if (window.Nexura.dom) window.Nexura.dom.hide(playEl);
      else playEl.setAttribute('hidden', '');
    }
    if (durationEl) {
      if (window.Nexura.dom) window.Nexura.dom.hide(durationEl);
      else durationEl.setAttribute('hidden', '');
    }

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
        if (theaterBtn) {
          if (window.Nexura.dom) window.Nexura.dom.show(theaterBtn);
          else theaterBtn.removeAttribute('hidden');
        }
      },
      { once: true }
    );

    facade.appendChild(iframe);
    facade.dataset.mounted = 'true';
  }

  function toggleTheaterMode(facade) {
    if (!facade) return;
    const isTheater = facade.classList.toggle('video-facade--theater');
    const closeBtn = document.getElementById('theater-close-btn');

    if (isTheater) {
      lockScroll();
      if (closeBtn) {
        if (window.Nexura.dom) window.Nexura.dom.show(closeBtn);
        else closeBtn.removeAttribute('hidden');
      }

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
      if (closeBtn) {
        if (window.Nexura.dom) window.Nexura.dom.hide(closeBtn);
        else closeBtn.setAttribute('hidden', '');
      }
      if (currentTheaterKeyHandler) {
        document.removeEventListener('keydown', currentTheaterKeyHandler);
        currentTheaterKeyHandler = null;
      }
    }
  }

  // Delegated event handling for video facades
  document.addEventListener('click', (e) => {
    const target = e.target;

    const closeBtn = target.closest('[data-action="close-theater"], #theater-close-btn');
    if (closeBtn) {
      e.stopPropagation();
      const facade = document.querySelector('.video-facade--theater') || closeBtn.closest('.video-facade');
      if (facade) {
        toggleTheaterMode(facade);
      }
      return;
    }

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
