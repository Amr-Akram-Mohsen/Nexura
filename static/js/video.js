/**
 * Nexura Phase 7 — YouTube Video Facade (video.js)
 * §24 — Lazy iframe mounting on explicit user click.
 *        No iframe is created until the user clicks the play button.
 */

'use strict';

// Global delegation — handled from core.js
// We just need to export the mount function that core.js can call,
// or we delegate here with a separate click listener on facade elements.

document.addEventListener('click', (e) => {
  const facade = e.target.closest('.video-facade[data-video-id]');
  if (!facade) return;

  // Already mounted? Don't double-mount
  if (facade.dataset.mounted === 'true') return;

  const videoId = facade.dataset.videoId;
  if (!videoId) return;

  // Hide thumb and play button
  const thumb = facade.querySelector('.video-facade__thumb');
  const playEl = facade.querySelector('.video-facade__play');
  const durationEl = facade.querySelector('.video-facade__duration');

  if (thumb) thumb.style.display = 'none';
  if (playEl) playEl.style.display = 'none';
  if (durationEl) durationEl.style.display = 'none';

  // Mount iframe
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
