/**
 * YouTube video facade: lazy mounts iframe on user click,
 * with loading spinner, ambient glow, and theater mode.
 */
'use strict';

/* ── Facade click → mount iframe with spinner ─────────────────────────────── */
if (typeof window.mountVideoFacade !== 'function') {
  document.addEventListener('click', (e) => {
    const facade = e.target.closest('.video-facade[data-video-id]');
    if (!facade || facade.dataset.mounted === 'true') return;

    const videoId = facade.dataset.videoId;
    if (!videoId) return;

    const thumb      = facade.querySelector('.video-facade__thumb');
    const playEl     = facade.querySelector('.video-facade__play');
    const durationEl = facade.querySelector('.video-facade__duration');
    const theaterBtn = facade.querySelector('.video-facade__theater-btn');

    // Show loading spinner
    const spinner = document.createElement('div');
    spinner.className = 'video-facade__spinner';
    spinner.innerHTML = '<div class="video-facade__spinner-ring"></div>';
    facade.appendChild(spinner);

    if (thumb)      thumb.style.display      = 'none';
    if (playEl)     playEl.style.display      = 'none';
    if (durationEl) durationEl.style.display  = 'none';

    const iframe = document.createElement('iframe');
    iframe.setAttribute('allow', 'autoplay; encrypted-media; picture-in-picture; fullscreen');
    iframe.setAttribute('allowfullscreen', '');
    iframe.setAttribute('loading', 'lazy');
    iframe.setAttribute('title', facade.dataset.videoTitle || 'YouTube Video');
    iframe.src = `https://www.youtube.com/embed/${encodeURIComponent(videoId)}?autoplay=1&rel=0&modestbranding=1`;

    // Remove spinner once iframe loads
    iframe.addEventListener('load', () => {
      spinner.remove();
      if (theaterBtn) theaterBtn.style.display = 'flex';
    }, { once: true });

    facade.appendChild(iframe);
    facade.dataset.mounted = 'true';
    facade.style.aspectRatio = '16/9';
  });
}

/* ── Theater Mode ─────────────────────────────────────────────────────────── */
window.toggleTheaterMode = function(facade) {
  const isTheater = facade.classList.toggle('video-facade--theater');

  // Create / remove the floating close button
  if (isTheater) {
    document.body.style.overflow = 'hidden';

    const closeBtn = document.createElement('button');
    closeBtn.className  = 'theater-close-btn';
    closeBtn.id         = 'theater-close-btn';
    closeBtn.setAttribute('aria-label', 'Exit theater mode');
    closeBtn.innerHTML  = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>`;
    closeBtn.addEventListener('click', () => window.toggleTheaterMode(facade));
    document.body.appendChild(closeBtn);

    // Keyboard: Escape closes theater
    const onKey = (e) => {
      if (e.key === 'Escape') {
        window.toggleTheaterMode(facade);
        document.removeEventListener('keydown', onKey);
      }
    };
    document.addEventListener('keydown', onKey);
  } else {
    document.body.style.overflow = '';
    const closeBtn = document.getElementById('theater-close-btn');
    if (closeBtn) closeBtn.remove();
  }
};
