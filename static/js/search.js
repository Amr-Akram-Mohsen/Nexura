/**
 * Nexura Phase 7 — Search Autocomplete + TreeWalker Highlighting (search.js)
 * §24 — Non-destructive text node highlighting using native TreeWalker.
 * §11.3 — Autocomplete API: /api/search/suggestions?q=... with 60s caching.
 */

'use strict';

// ─── Autocomplete ────────────────────────────────────────────────────────────
const SearchAutocomplete = {
  input: null,
  dropdown: null,
  localCache: new Map(),
  debounceTimer: null,
  DEBOUNCE_MS: 200,
  MIN_CHARS: 2,
  currentQuery: '',

  init() {
    this.input    = document.querySelector('#search-input, [data-search-input]');
    this.dropdown = document.querySelector('#autocomplete-dropdown, [data-search-dropdown]');
    if (!this.input || !this.dropdown) return;

    this.input.addEventListener('input', () => this._onInput());
    this.input.addEventListener('keydown', (e) => this._onKeydown(e));
    this.input.addEventListener('focus', () => {
      if (this.input.value.trim().length >= this.MIN_CHARS) this._open();
    });
    document.addEventListener('click', (e) => {
      if (!this.input.contains(e.target) && !this.dropdown.contains(e.target)) {
        this._close();
      }
    });
  },

  _onInput() {
    clearTimeout(this.debounceTimer);
    const q = this.input.value.trim();
    if (q.length < this.MIN_CHARS) { this._close(); return; }
    this.debounceTimer = setTimeout(() => this._fetch(q), this.DEBOUNCE_MS);
  },

  _onKeydown(e) {
    if (!this.dropdown.classList.contains('open')) return;
    const items = [...this.dropdown.querySelectorAll('.autocomplete-item')];
    const focusedIdx = items.findIndex(i => i.classList.contains('focused'));

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const next = focusedIdx < items.length - 1 ? focusedIdx + 1 : 0;
      items.forEach((i, idx) => i.classList.toggle('focused', idx === next));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prev = focusedIdx > 0 ? focusedIdx - 1 : items.length - 1;
      items.forEach((i, idx) => i.classList.toggle('focused', idx === prev));
    } else if (e.key === 'Enter') {
      const focused = items[focusedIdx];
      if (focused) {
        e.preventDefault();
        const link = focused.closest('a') || focused.querySelector('a');
        if (link) window.location.href = link.href;
      }
    } else if (e.key === 'Escape') {
      this._close();
    }
  },

  async _fetch(q) {
    this.currentQuery = q;
    if (this.localCache.has(q)) {
      this._render(q, this.localCache.get(q));
      return;
    }

    try {
      const res = await fetch(`/api/search/suggestions?q=${encodeURIComponent(q)}`);
      if (!res.ok) return;
      const data = await res.json();
      this.localCache.set(q, data);
      if (this.currentQuery === q) this._render(q, data);
    } catch {
      // Silently fail — search still works via form submit
    }
  },

  _render(q, data) {
    const articles = data.articles || [];
    const videos   = data.videos   || [];

    if (!articles.length && !videos.length) { this._close(); return; }

    let html = '';

    if (articles.length) {
      html += `<div class="autocomplete-section-title">Articles</div>`;
      html += articles.map(item => `
        <a class="autocomplete-item" href="${this._esc(item.url)}" data-type="article">
          ${item.thumb ? `<img class="autocomplete-item__thumb" src="${this._esc(item.thumb)}" alt="" loading="lazy">` : `<div class="autocomplete-item__thumb"></div>`}
          <div class="autocomplete-item__text">
            <div class="autocomplete-item__title">${this._esc(item.title)}</div>
            ${item.category ? `<div class="autocomplete-item__category">${this._esc(item.category)}</div>` : ''}
          </div>
        </a>`).join('');
    }

    if (videos.length) {
      html += `<div class="autocomplete-section-title">Videos</div>`;
      html += videos.map(item => `
        <a class="autocomplete-item" href="${this._esc(item.url)}" data-type="video">
          ${item.thumb ? `<img class="autocomplete-item__thumb" src="${this._esc(item.thumb)}" alt="" loading="lazy">` : `<div class="autocomplete-item__thumb"></div>`}
          <div class="autocomplete-item__text">
            <div class="autocomplete-item__title">${this._esc(item.title)}</div>
            ${item.channel ? `<div class="autocomplete-item__category">${this._esc(item.channel)}</div>` : ''}
          </div>
        </a>`).join('');
    }

    this.dropdown.innerHTML = html;
    this._open();
  },

  _open()  { this.dropdown.classList.add('open'); },
  _close() { this.dropdown.classList.remove('open'); },
  _esc(s)  { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); },
};

// ─── TreeWalker Search Highlighting (§24) ───────────────────────────────────
const SearchHighlighter = {
  /**
   * Highlights all occurrences of `query` within `rootEl`
   * using a native TreeWalker that traverses text nodes only.
   * Never touches innerHTML on nodes that contain event listeners.
   */
  highlight(rootEl, query) {
    if (!rootEl || !query || query.length < 2) return;

    this.removeHighlights(rootEl);

    const pattern = new RegExp(`(${this._escapeRegex(query)})`, 'gi');
    const walker = document.createTreeWalker(
      rootEl,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          const parent = node.parentElement;
          if (!parent) return NodeFilter.FILTER_REJECT;
          const tag = parent.tagName.toUpperCase();
          if (['SCRIPT','STYLE','NOSCRIPT','MARK'].includes(tag)) {
            return NodeFilter.FILTER_REJECT;
          }
          return pattern.test(node.nodeValue)
            ? NodeFilter.FILTER_ACCEPT
            : NodeFilter.FILTER_SKIP;
        }
      }
    );

    const textNodes = [];
    while (walker.nextNode()) {
      textNodes.push(walker.currentNode);
      // Reset lastIndex since test() advances it
      pattern.lastIndex = 0;
    }

    textNodes.forEach(node => {
      const parts = node.nodeValue.split(pattern);
      const frag = document.createDocumentFragment();
      parts.forEach(part => {
        if (pattern.test(part)) {
          const mark = document.createElement('mark');
          mark.dataset.highlight = '';
          mark.textContent = part;
          frag.appendChild(mark);
        } else {
          frag.appendChild(document.createTextNode(part));
        }
        pattern.lastIndex = 0;
      });
      node.parentNode.replaceChild(frag, node);
    });
  },

  removeHighlights(rootEl) {
    rootEl.querySelectorAll('mark[data-highlight]').forEach(mark => {
      const parent = mark.parentNode;
      parent.replaceChild(document.createTextNode(mark.textContent), mark);
      parent.normalize();
    });
  },

  _escapeRegex(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  },
};

// ─── Search Results Page Highlighting ───────────────────────────────────────
function initSearchHighlighting() {
  const q = new URLSearchParams(window.location.search).get('q');
  if (!q) return;

  const resultsContainer = document.querySelector('[data-search-results]');
  if (resultsContainer) {
    SearchHighlighter.highlight(resultsContainer, q);
  }
}

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  SearchAutocomplete.init();
  initSearchHighlighting();
});

// Export for use in other modules if needed
window.SearchHighlighter = SearchHighlighter;
