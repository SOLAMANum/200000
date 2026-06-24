/**
 * app.js — Product Catalog Frontend
 *
 * Cursor-based pagination:  each API response includes a `next_cursor` string.
 * We keep a stack of cursors so the user can page backward too.  The cursor
 * encodes the (created_at, id) of the last row on the current page; the server
 * uses it to fetch the next page with a WHERE clause rather than OFFSET.
 */

const API_BASE = 'http://localhost:8000/api';

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  cursorStack: [],   // stack of cursors: cursorStack[0] = null (page 1), cursorStack[1] = cursor for page 2 …
  currentCursor: null,
  nextCursor: null,
  hasMore: false,
  pageNumber: 1,
  category: '',
  limit: 20,
  loading: false,
};

// ── DOM refs ───────────────────────────────────────────────────────────────
const grid        = document.getElementById('product-grid');
const btnPrev     = document.getElementById('btn-prev');
const btnNext     = document.getElementById('btn-next');
const pageInfo    = document.getElementById('page-info');
const catSelect   = document.getElementById('category-select');
const limitSelect = document.getElementById('limit-select');
const resultCount = document.getElementById('result-count');
const headerMeta  = document.getElementById('header-meta');
const toast       = document.getElementById('toast');

// ── Utility ────────────────────────────────────────────────────────────────
function formatPrice(price) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(price);
}

function formatDate(isoString) {
  return new Date(isoString).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  });
}

let toastTimer;
function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3000);
}

// ── Skeleton helpers ───────────────────────────────────────────────────────
function renderSkeletons(count) {
  grid.innerHTML = Array.from({ length: count }, () =>
    `<div class="skeleton-card" aria-hidden="true"></div>`
  ).join('');
}

// ── Render products ────────────────────────────────────────────────────────
function renderProducts(products) {
  if (!products.length) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="empty-state-icon">◈</div>
        <h3>No products found</h3>
        <p>Try a different category or reset your filters.</p>
      </div>`;
    return;
  }

  grid.innerHTML = products.map((p, i) => `
    <article
      class="product-card"
      id="product-${p.id}"
      style="animation-delay:${i * 18}ms"
      aria-label="${escapeHtml(p.name)}, ${formatPrice(p.price)}"
    >
      <div class="card-category">${escapeHtml(p.category)}</div>
      <h2 class="card-name">${escapeHtml(p.name)}</h2>
      <div class="card-footer">
        <span class="card-price">${formatPrice(p.price)}</span>
        <span class="card-id">#${p.id}</span>
      </div>
      <div class="card-date">Added ${formatDate(p.created_at)}</div>
    </article>
  `).join('');
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Fetch a page ───────────────────────────────────────────────────────────
async function fetchPage(cursor) {
  if (state.loading) return;
  state.loading = true;
  renderSkeletons(state.limit);
  btnPrev.disabled = true;
  btnNext.disabled = true;

  const params = new URLSearchParams({ limit: state.limit });
  if (cursor)         params.set('cursor', cursor);
  if (state.category) params.set('category', state.category);

  const url = `${API_BASE}/products?${params}`;

  try {
    const t0 = performance.now();
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    const elapsed = Math.round(performance.now() - t0);

    state.nextCursor = json.pagination.next_cursor;
    state.hasMore    = json.pagination.has_more;

    renderProducts(json.data);
    updatePaginationUI();

    const shown = json.data.length;
    resultCount.textContent = shown
      ? `Showing ${shown} product${shown !== 1 ? 's' : ''} — ${elapsed}ms`
      : '';

  } catch (err) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="empty-state-icon">⚠</div>
        <h3>Could not load products</h3>
        <p>${escapeHtml(err.message)}</p>
      </div>`;
    showToast(`Error: ${err.message}`);
    updatePaginationUI();
  } finally {
    state.loading = false;
  }
}

// ── Pagination UI ──────────────────────────────────────────────────────────
function updatePaginationUI() {
  btnPrev.disabled = state.pageNumber <= 1;
  btnNext.disabled = !state.hasMore;
  pageInfo.textContent = `Page ${state.pageNumber}`;
}

// ── Navigation ─────────────────────────────────────────────────────────────
function goNext() {
  if (!state.hasMore || state.loading) return;
  // Push current cursor onto stack so we can come back
  state.cursorStack.push(state.currentCursor);
  state.currentCursor = state.nextCursor;
  state.pageNumber++;
  fetchPage(state.currentCursor);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function goPrev() {
  if (state.pageNumber <= 1 || state.loading) return;
  state.currentCursor = state.cursorStack.pop();
  state.pageNumber--;
  fetchPage(state.currentCursor);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Reset & reload ─────────────────────────────────────────────────────────
function reset() {
  state.cursorStack   = [];
  state.currentCursor = null;
  state.nextCursor    = null;
  state.hasMore       = false;
  state.pageNumber    = 1;
}

// ── Load categories ────────────────────────────────────────────────────────
async function loadCategories() {
  try {
    const res  = await fetch(`${API_BASE}/categories`);
    const data = await res.json();

    const total = data.reduce((s, c) => s + c.count, 0);
    headerMeta.textContent = `${total.toLocaleString()} products`;

    data.forEach(({ category, count }) => {
      const opt = document.createElement('option');
      opt.value       = category;
      opt.textContent = `${category} (${count.toLocaleString()})`;
      catSelect.appendChild(opt);
    });
  } catch {
    /* silently degrade — categories are non-critical */
  }
}

// ── Event listeners ────────────────────────────────────────────────────────
btnNext.addEventListener('click', goNext);
btnPrev.addEventListener('click', goPrev);

catSelect.addEventListener('change', () => {
  state.category = catSelect.value;
  reset();
  fetchPage(null);
});

limitSelect.addEventListener('change', () => {
  state.limit = Number(limitSelect.value);
  reset();
  fetchPage(null);
});

// ── Boot ───────────────────────────────────────────────────────────────────
(async () => {
  await loadCategories();
  fetchPage(null);
})();
