/**
 * YouTube video facade: lazy mounts iframe on user click.
 */
'use strict';

if (typeof window.mountVideoFacade !== 'function') {
  document.addEventListener('click', (e) => {
    const facade = e.target.closest('.video-facade[data-video-id]');
    if (!facade || facade.dataset.mounted === 'true') return;

    const videoId = facade.dataset.videoId;
    if (!videoId) return;

    const thumb = facade.querySelector('.video-facade__thumb');
    const playEl = facade.querySelector('.video-facade__play');
    const durationEl = facade.querySelector('.video-facade__duration');

    if (thumb) thumb.style.display = 'none';
    if (playEl) playEl.style.display = 'none';
    if (durationEl) durationEl.style.display = 'none';

    const iframe = document.createElement('iframe');
    iframe.setAttribute('allow', 'autoplay; encrypted-media; picture-in-picture; fullscreen');
    iframe.setAttribute('allowfullscreen', '');
    iframe.setAttribute('loading', 'lazy');
    iframe.setAttribute('title', facade.dataset.videoTitle || 'YouTube Video');
    iframe.src = `https://www.youtube.com/embed/${encodeURIComponent(videoId)}?autoplay=1&rel=0&modestbranding=1`;

    facade.appendChild(iframe);
    facade.dataset.mounted = 'true';
    facade.style.aspectRatio = '16/9';
  });
}
