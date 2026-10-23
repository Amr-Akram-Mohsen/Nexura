/** Search autocomplete suggestions and DOM text highlighting. */
'use strict';

const SearchAutocomplete = {
  input: null,
  dropdown: null,
  localCache: new Map(),
  debounceTimer: null,
  DEBOUNCE_MS: 200,
  MIN_CHARS: 2,
  currentQuery: '',

  init() {
    this.input = document.querySelector('#search-input, [data-search-input]');
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
    if (q.length < this.MIN_CHARS) {
      this._close();
      return;
    }
    this.debounceTimer = setTimeout(() => this._fetch(q), this.DEBOUNCE_MS);
  },

  _onKeydown(e) {
    if (!this.dropdown.classList.contains('open')) return;
    const items = [...this.dropdown.querySelectorAll('.autocomplete-item')];
    const focusedIdx = items.findIndex((i) => i.classList.contains('focused'));

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

    this._showSkeleton();

    try {
      const res = await fetch(`/api/search/suggestions?q=${encodeURIComponent(q)}`);
      if (!res.ok) {
        this._close();
        return;
      }
      const data = await res.json();
      this.localCache.set(q, data);
      if (this.currentQuery === q) this._render(q, data);
    } catch {
      this._close();
    }
  },

  _createSkeletonRow() {
    const tpl = document.getElementById('search-skeleton-row-template');
    if (tpl && tpl.content) {
      return tpl.content.firstElementChild.cloneNode(true);
    }
    const skeleton = document.createElement('div');
    skeleton.className = 'autocomplete-skeleton';
    skeleton.setAttribute('aria-hidden', 'true');
    return skeleton;
  },

  _showSkeleton() {
    const frag = document.createDocumentFragment();
    for (let i = 0; i < 3; i++) {
      frag.appendChild(this._createSkeletonRow());
    }
    this.dropdown.replaceChildren(frag);
    this._open();
  },

  _createItem(item, type) {
    const tpl = document.getElementById('search-item-template');
    let a;
    if (tpl && tpl.content) {
      a = tpl.content.firstElementChild.cloneNode(true);
    } else {
      a = document.createElement('a');
      a.className = 'autocomplete-item';
    }

    if (item.url && (item.url.startsWith('/') || item.url.startsWith('http://') || item.url.startsWith('https://'))) {
      a.href = item.url;
    } else {
      a.href = '#';
    }
    a.dataset.type = type;

    const thumbEl = a.querySelector('.autocomplete-item__thumb');
    if (thumbEl) {
      if (item.thumb && (item.thumb.startsWith('/') || item.thumb.startsWith('http://') || item.thumb.startsWith('https://'))) {
        const img = document.createElement('img');
        img.className = 'autocomplete-item__thumb';
        img.src = item.thumb;
        img.alt = '';
        img.loading = 'lazy';
        thumbEl.replaceWith(img);
      }
    }

    const titleDiv = a.querySelector('.autocomplete-item__title');
    if (titleDiv) {
      titleDiv.textContent = item.title || '';
    }

    const categoryText = type === 'article' ? item.category : item.channel;
    const categoryDiv = a.querySelector('.autocomplete-item__category');
    if (categoryDiv) {
      if (categoryText) {
        categoryDiv.textContent = categoryText;
      } else {
        categoryDiv.remove();
      }
    }

    const badge = a.querySelector('.autocomplete-item__badge');
    if (badge) {
      badge.className = `autocomplete-item__badge autocomplete-item__badge--${type}`;
      badge.textContent = type === 'article' ? 'Article' : 'Video';
    }

    return a;
  },

  _createFooter(q) {
    const tpl = document.getElementById('search-footer-template');
    if (tpl && tpl.content) {
      const footer = tpl.content.firstElementChild.cloneNode(true);
      footer.href = `/search?q=${encodeURIComponent(q)}`;
      const queryEl = footer.querySelector('.autocomplete-footer__query');
      if (queryEl) {
        queryEl.textContent = `“${q}”`;
      }
      return footer;
    }
    const footer = document.createElement('a');
    footer.className = 'autocomplete-footer';
    footer.href = `/search?q=${encodeURIComponent(q)}`;
    footer.textContent = `View all results for “${q}”`;
    return footer;
  },

  _render(q, data) {
    const articles = data.articles || [];
    const videos = data.videos || [];

    if (!articles.length && !videos.length) {
      this._close();
      return;
    }

    const frag = document.createDocumentFragment();

    if (articles.length) {
      const sectionTitle = document.createElement('div');
      sectionTitle.className = 'autocomplete-section-title';
      sectionTitle.textContent = 'Articles';
      frag.appendChild(sectionTitle);

      articles.forEach((item) => {
        frag.appendChild(this._createItem(item, 'article'));
      });
    }

    if (videos.length) {
      const sectionTitle = document.createElement('div');
      sectionTitle.className = 'autocomplete-section-title';
      sectionTitle.textContent = 'Videos';
      frag.appendChild(sectionTitle);

      videos.forEach((item) => {
        frag.appendChild(this._createItem(item, 'video'));
      });
    }

    frag.appendChild(this._createFooter(q));

    this.dropdown.replaceChildren(frag);
    this._open();
  },

  _open() {
    this.dropdown.classList.add('open');
  },
  _close() {
    this.dropdown.classList.remove('open');
  },
  _esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  },
};

const SearchHighlighter = {
  highlight(rootEl, query) {
    if (!rootEl || !query || query.length < 2) return;

    this.removeHighlights(rootEl);

    const pattern = new RegExp(`(${this._escapeRegex(query)})`, 'gi');
    const walker = document.createTreeWalker(rootEl, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent) return NodeFilter.FILTER_REJECT;
        const tag = parent.tagName.toUpperCase();
        if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'MARK'].includes(tag)) {
          return NodeFilter.FILTER_REJECT;
        }
        return pattern.test(node.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      },
    });

    const textNodes = [];
    while (walker.nextNode()) {
      textNodes.push(walker.currentNode);
      pattern.lastIndex = 0;
    }

    textNodes.forEach((node) => {
      const parts = node.nodeValue.split(pattern);
      const frag = document.createDocumentFragment();
      parts.forEach((part) => {
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
    rootEl.querySelectorAll('mark[data-highlight]').forEach((mark) => {
      const parent = mark.parentNode;
      parent.replaceChild(document.createTextNode(mark.textContent), mark);
      parent.normalize();
    });
  },

  _escapeRegex(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  },
};

function initSearchHighlighting() {
  const q = new URLSearchParams(window.location.search).get('q');
  if (!q) return;

  const resultsContainer = document.querySelector('[data-search-results]');
  if (resultsContainer) {
    SearchHighlighter.highlight(resultsContainer, q);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  SearchAutocomplete.init();
  initSearchHighlighting();
});

window.SearchHighlighter = SearchHighlighter;
