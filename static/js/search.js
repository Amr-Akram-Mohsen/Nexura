/** Search autocomplete suggestions, DOM text highlighting, and live UI controls. */
'use strict';

const SearchAutocomplete = {
  input: null,
  dropdown: null,
  clearBtn: null,
  localCache: new Map(),
  debounceTimer: null,
  abortController: null,
  DEBOUNCE_MS: 180,
  MIN_CHARS: 2,
  currentQuery: '',

  init() {
    this.input = document.querySelector('#search-input, [data-search-input]');
    this.dropdown = document.querySelector('#autocomplete-dropdown, [data-search-dropdown]');
    this.clearBtn = document.getElementById('search-clear-btn');

    if (!this.input || !this.dropdown) return;

    // Bind all input-level events
    this.input.addEventListener('input', () => this._onInput());
    this.input.addEventListener('keydown', (e) => this._onKeydown(e));
    this.input.addEventListener('focus', () => {
      if (this.input.value.trim().length >= this.MIN_CHARS) this._open();
    });

    // Close on outside click (delegated once on document)
    document.addEventListener('click', (e) => {
      if (!this.input.contains(e.target) && !this.dropdown.contains(e.target)) {
        this._close();
      }
    });

    // Clear button
    if (this.clearBtn) {
      this.clearBtn.addEventListener('click', () => {
        this.input.value = '';
        this.input.focus();
        this._syncClearBtn();
        this._close();
      });
    }

    // Sync clear button initial state (e.g. when page loads with a query value)
    this._syncClearBtn();
  },

  _syncClearBtn() {
    if (!this.clearBtn) return;
    const hasValue = this.input.value.trim().length > 0;
    if (hasValue) {
      this.clearBtn.removeAttribute('hidden');
    } else {
      this.clearBtn.setAttribute('hidden', '');
    }
  },

  _onInput() {
    clearTimeout(this.debounceTimer);
    const q = this.input.value.trim();
    this._syncClearBtn();

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
      items[next]?.scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prev = focusedIdx > 0 ? focusedIdx - 1 : items.length - 1;
      items.forEach((i, idx) => i.classList.toggle('focused', idx === prev));
      items[prev]?.scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter') {
      const focused = items[focusedIdx];
      if (focused) {
        e.preventDefault();
        const link = focused.closest('a') || focused.querySelector('a');
        if (link) window.location.href = link.href;
      }
    } else if (e.key === 'Escape') {
      this._close();
      this.input.focus();
    }
  },

  async _fetch(q) {
    this.currentQuery = q;

    // Cache hit
    if (this.localCache.has(q)) {
      this._render(q, this.localCache.get(q));
      return;
    }

    // Cancel any in-flight request
    if (this.abortController) {
      this.abortController.abort();
    }
    this.abortController = new AbortController();

    this._showSkeleton();

    try {
      const res = await fetch(`/api/search/suggestions?q=${encodeURIComponent(q)}`, {
        signal: this.abortController.signal,
      });
      if (!res.ok) {
        this._close();
        return;
      }
      const data = await res.json();
      this.localCache.set(q, data);
      if (this.currentQuery === q) this._render(q, data);
    } catch (err) {
      if (err.name !== 'AbortError') this._close();
    } finally {
      this.abortController = null;
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
    const thumb = document.createElement('div');
    thumb.className = 'autocomplete-skeleton__thumb';
    const lines = document.createElement('div');
    lines.className = 'autocomplete-skeleton__lines';
    const l1 = document.createElement('div');
    l1.className = 'autocomplete-skeleton__line';
    const l2 = document.createElement('div');
    l2.className = 'autocomplete-skeleton__line autocomplete-skeleton__line--short';
    lines.append(l1, l2);
    skeleton.append(thumb, lines);
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
        queryEl.textContent = `"${q}"`;
      }
      return footer;
    }
    const footer = document.createElement('a');
    footer.className = 'autocomplete-footer';
    footer.href = `/search?q=${encodeURIComponent(q)}`;
    footer.textContent = `View all results for "${q}"`;
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
      articles.forEach((item) => frag.appendChild(this._createItem(item, 'article')));
    }

    if (videos.length) {
      const sectionTitle = document.createElement('div');
      sectionTitle.className = 'autocomplete-section-title';
      sectionTitle.textContent = 'Videos';
      frag.appendChild(sectionTitle);
      videos.forEach((item) => frag.appendChild(this._createItem(item, 'video')));
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
