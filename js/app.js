/* ── State ─────────────────────────────────────────────────────────── */

let allVehicles = [];
let filtered = [];
let activeType = 'all';
let activeSortKey = 'range';
let searchQuery = '';

/* ── Type config ───────────────────────────────────────────────────── */

const TYPE_ICONS = {
  sedan:      '🚗',
  suv:        '🚙',
  truck:      '🛻',
  sports:     '🏎️',
  motorcycle: '🏍️',
  van:        '🚐',
  bus:        '🚌',
  commercial: '🚚',
};

const COUNTRY_FLAGS = {
  'USA':         '🇺🇸',
  'Germany':     '🇩🇪',
  'South Korea': '🇰🇷',
  'China':       '🇨🇳',
  'Japan':       '🇯🇵',
  'Sweden':      '🇸🇪',
  'UK':          '🇬🇧',
  'Italy':       '🇮🇹',
  'Croatia':     '🇭🇷',
  'Canada':      '🇨🇦',
  'France':      '🇫🇷',
  'Norway':      '🇳🇴',
};

function countryFlag(country) {
  return COUNTRY_FLAGS[country] || '🌍';
}

/* ── Data loading ──────────────────────────────────────────────────── */

async function loadVehicles() {
  try {
    const resp = await fetch('data/vehicles.json');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    allVehicles = data.vehicles || [];

    // Update header stats
    document.getElementById('stat-count').textContent = data.vehicle_count || allVehicles.length;
    const updated = formatDate(data.last_updated);
    document.getElementById('stat-updated').textContent = updated;
    document.getElementById('footer-updated').textContent = data.last_updated
      ? new Date(data.last_updated).toUTCString()
      : '—';

    applyFilters();
  } catch (err) {
    document.getElementById('vehicle-grid').innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <h3>Failed to load vehicles</h3>
        <p>${err.message}</p>
      </div>`;
  }
}

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/* ── Filtering & sorting ───────────────────────────────────────────── */

function applyFilters() {
  let list = allVehicles;

  if (activeType !== 'all') {
    list = list.filter(v => v.type === activeType);
  }

  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    list = list.filter(v =>
      v.make.toLowerCase().includes(q) ||
      v.model.toLowerCase().includes(q) ||
      (v.variant || '').toLowerCase().includes(q) ||
      v.country.toLowerCase().includes(q) ||
      v.type.toLowerCase().includes(q)
    );
  }

  list = [...list].sort(getSorter(activeSortKey));

  filtered = list;
  renderGrid(filtered);
  updateResultsText();
}

function getSorter(key) {
  switch (key) {
    case 'range':        return (a, b) => (b.range_mi || 0) - (a.range_mi || 0);
    case 'price_asc':   return (a, b) => (a.price_usd ?? Infinity) - (b.price_usd ?? Infinity);
    case 'price_desc':  return (a, b) => (b.price_usd ?? -Infinity) - (a.price_usd ?? -Infinity);
    case 'battery':     return (a, b) => (b.battery_kwh || 0) - (a.battery_kwh || 0);
    case 'acceleration':
      return (a, b) => {
        const aVal = a.acceleration_0_60_sec ?? 99;
        const bVal = b.acceleration_0_60_sec ?? 99;
        return aVal - bVal;
      };
    case 'year': return (a, b) => (b.year || 0) - (a.year || 0);
    default:     return () => 0;
  }
}

function updateResultsText() {
  const el = document.getElementById('results-text');
  const total = allVehicles.length;
  const shown = filtered.length;
  if (shown === total) {
    el.innerHTML = `Showing all <strong>${total}</strong> vehicles`;
  } else {
    el.innerHTML = `Showing <strong>${shown}</strong> of ${total} vehicles`;
  }
}

/* ── Rendering ─────────────────────────────────────────────────────── */

function renderGrid(vehicles) {
  const grid = document.getElementById('vehicle-grid');

  if (vehicles.length === 0) {
    grid.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">🔍</div>
        <h3>No vehicles found</h3>
        <p>Try adjusting your filters or search query.</p>
      </div>`;
    return;
  }

  grid.innerHTML = '';
  const fragment = document.createDocumentFragment();
  vehicles.forEach(v => fragment.appendChild(createCard(v)));
  grid.appendChild(fragment);
}

function createCard(v) {
  const card = document.createElement('article');
  card.className = 'vehicle-card';
  card.setAttribute('role', 'button');
  card.setAttribute('tabindex', '0');
  card.setAttribute('aria-label', `${v.year} ${v.make} ${v.model}`);

  const hasImg = !!v.image_url;
  card.innerHTML = `
    <div class="card-image" data-type="${v.type}">
      ${hasImg ? `<img src="${escAttr(v.image_url)}" alt="${escAttr(v.year + ' ' + v.make + ' ' + v.model)}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'" />` : ''}
      <div class="card-image-placeholder" style="${hasImg ? 'display:none' : 'display:flex'}">
        <div class="placeholder-icon">${TYPE_ICONS[v.type] || '🚗'}</div>
        <div class="placeholder-name">${escHtml(v.make)} ${escHtml(v.model)}</div>
      </div>
      <span class="card-type-badge">${TYPE_ICONS[v.type] || '🚗'} ${v.type}</span>
      <span class="card-country-badge">${countryFlag(v.country)} ${v.country}</span>
    </div>
    <div class="card-body">
      <div class="card-header">
        <div class="card-make">${escHtml(v.make)}</div>
        <div class="card-model">${escHtml(v.model)}</div>
        ${v.variant ? `<div class="card-variant">${escHtml(v.variant)}</div>` : ''}
      </div>
      <div class="card-specs">
        <div class="spec-item highlight">
          <div class="spec-label">Range</div>
          <div class="spec-value">${v.range_mi ?? '—'}<span class="spec-unit"> mi</span></div>
        </div>
        <div class="spec-item">
          <div class="spec-label">Battery</div>
          <div class="spec-value">${v.battery_kwh ?? '—'}<span class="spec-unit"> kWh</span></div>
        </div>
        <div class="spec-item">
          <div class="spec-label">0–60 mph</div>
          <div class="spec-value">${v.acceleration_0_60_sec != null ? v.acceleration_0_60_sec + '<span class="spec-unit">s</span>' : '—'}</div>
        </div>
        <div class="spec-item">
          <div class="spec-label">Top Speed</div>
          <div class="spec-value">${v.top_speed_mph != null ? v.top_speed_mph + '<span class="spec-unit"> mph</span>' : '—'}</div>
        </div>
      </div>
      <div class="card-footer">
        ${priceHTML(v.price_usd)}
        <span class="card-year">${v.year}</span>
      </div>
    </div>`;

  card.addEventListener('click', () => openModal(v));
  card.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') openModal(v); });
  return card;
}

function priceHTML(price) {
  if (price == null) return '<span class="card-price na">Price TBD</span>';
  return `<span class="card-price">$${price.toLocaleString('en-US')}</span>`;
}

/* ── Modal ─────────────────────────────────────────────────────────── */

function openModal(v) {
  const overlay = document.getElementById('modal-overlay');
  const modalImg = document.getElementById('modal-image');
  const closeBtn = document.getElementById('modal-close');

  // Image
  modalImg.setAttribute('data-type', v.type);
  const hasImg = !!v.image_url;
  modalImg.innerHTML = hasImg
    ? `<img src="${escAttr(v.image_url)}" alt="${escAttr(v.year + ' ' + v.make + ' ' + v.model)}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'" />
       <div class="card-image-placeholder" style="display:none;height:240px">
         <div class="placeholder-icon">${TYPE_ICONS[v.type] || '🚗'}</div>
         <div class="placeholder-name">${escHtml(v.make)} ${escHtml(v.model)}</div>
       </div>`
    : `<div class="card-image-placeholder" style="display:flex;height:240px">
         <div class="placeholder-icon">${TYPE_ICONS[v.type] || '🚗'}</div>
         <div class="placeholder-name">${escHtml(v.make)} ${escHtml(v.model)}</div>
       </div>`;
  const newClose = document.createElement('button');
  newClose.className = 'modal-close';
  newClose.id = 'modal-close';
  newClose.setAttribute('aria-label', 'Close');
  newClose.textContent = '✕';
  newClose.addEventListener('click', closeModal);
  modalImg.appendChild(newClose);

  document.getElementById('modal-make').textContent = v.make;
  document.getElementById('modal-title').textContent = v.model;
  document.getElementById('modal-subtitle').textContent =
    [v.variant, v.year].filter(Boolean).join(' · ');
  document.getElementById('modal-description').textContent =
    v.description || 'No description available.';

  // Specs
  const specs = [
    { label: 'Range', value: v.range_mi, unit: 'mi', highlight: true },
    { label: 'Range (km)', value: v.range_km, unit: 'km' },
    { label: 'Battery', value: v.battery_kwh, unit: 'kWh' },
    { label: '0–60 mph', value: v.acceleration_0_60_sec, unit: 's' },
    { label: 'Top Speed', value: v.top_speed_mph, unit: 'mph' },
    { label: 'Max DC Charge', value: v.dc_fast_charge_kw, unit: 'kW' },
    { label: '10→80% Time', value: v.charge_time_10_80_min, unit: 'min' },
    { label: 'Top Speed (km/h)', value: v.top_speed_kmh, unit: 'km/h' },
    { label: 'Starting Price', value: v.price_usd != null ? '$' + v.price_usd.toLocaleString('en-US') : null, unit: '', raw: true },
  ];

  const specsGrid = document.getElementById('modal-specs-grid');
  specsGrid.innerHTML = specs.map(s => `
    <div class="modal-spec${s.highlight ? ' highlight' : ''}">
      <div class="modal-spec-label">${s.label}</div>
      <div class="modal-spec-value">
        ${s.value != null ? (s.raw ? s.value : s.value + `<span class="modal-spec-unit"> ${s.unit}</span>`) : '<span style="color:var(--text-tertiary);font-size:14px">—</span>'}
      </div>
    </div>`).join('');

  // Meta tags
  const meta = document.getElementById('modal-meta');
  meta.innerHTML = `
    <div class="meta-tag">${countryFlag(v.country)} ${escHtml(v.country)}</div>
    <div class="meta-tag">${TYPE_ICONS[v.type] || ''} ${v.type}</div>
    <div class="meta-tag">📅 ${v.year}</div>
    <div class="meta-tag ${v.global_availability ? 'global' : ''}">
      ${v.global_availability ? '🌍 Global availability' : '🏠 Regional only'}
    </div>`;

  overlay.classList.add('open');
  document.body.style.overflow = 'hidden';

  // Focus trap
  const modal = document.getElementById('modal');
  modal.querySelector('.modal-close').focus();
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
  document.body.style.overflow = '';
}

/* ── Events ────────────────────────────────────────────────────────── */

document.getElementById('modal-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('modal-overlay')) closeModal();
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

document.getElementById('filter-group').addEventListener('click', e => {
  const btn = e.target.closest('.filter-btn');
  if (!btn) return;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  activeType = btn.dataset.type;
  applyFilters();
});

document.getElementById('sort-select').addEventListener('change', e => {
  activeSortKey = e.target.value;
  applyFilters();
});

let searchTimer;
document.getElementById('search-input').addEventListener('input', e => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchQuery = e.target.value.trim();
    applyFilters();
  }, 180);
});

/* ── Helpers ───────────────────────────────────────────────────────── */

function escHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function escAttr(str) {
  return escHtml(str).replace(/'/g, '&#39;');
}

/* ── Init ──────────────────────────────────────────────────────────── */

loadVehicles();
