/**
 * LoanSphere — Extractor JS
 * Handles file upload, API call, and color-coded clause rendering with filter bar
 */

const uploadZone     = document.getElementById('uploadZone');
const fileInput      = document.getElementById('fileInput');
const uploadTitle    = document.getElementById('uploadTitle');
const extractBtn     = document.getElementById('extractBtn');
const btnIcon        = document.getElementById('btnIcon');
const btnLabel       = document.getElementById('btnLabel');
const statusMsg      = document.getElementById('statusMsg');
const resultsSection = document.getElementById('resultsSection');
const clausesList    = document.getElementById('clausesList');
const clauseCount    = document.getElementById('clauseCount');
const docIdBadge     = document.getElementById('docIdBadge');
const statsBar       = document.getElementById('statsBar');
const filterBar      = document.getElementById('filterBar');
const clauseLegend   = document.getElementById('clauseLegend');

let selectedFile  = null;
let allClauses    = [];
let activeFilter  = 'ALL';

// Clause colours (must match CSS variables)
const CLAUSE_META = {
  INTEREST:      { emoji: '💰', label: 'Interest',      color: '#2563eb' },
  REPAYMENT:     { emoji: '📅', label: 'Repayment',     color: '#059669' },
  PENALTY:       { emoji: '⚠️', label: 'Penalty',       color: '#dc2626' },
  COLLATERAL:    { emoji: '🏠', label: 'Collateral',    color: '#7c3aed' },
  PREPAYMENT:    { emoji: '⏩', label: 'Prepayment',    color: '#d97706' },
  GOVERNING_LAW: { emoji: '⚖️', label: 'Governing Law', color: '#0891b2' },
  TERMINATION:   { emoji: '🔚', label: 'Termination',   color: '#be185d' },
};

// ── Drag & drop ───────────────────────────────────────────────
uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('ls-upload-zone--drag'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('ls-upload-zone--drag'));
uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('ls-upload-zone--drag');
  if (e.dataTransfer.files[0]) handleFileSelection(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => { if (fileInput.files[0]) handleFileSelection(fileInput.files[0]); });

function handleFileSelection(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['pdf', 'docx'].includes(ext)) { showStatus('error', '⚠️ Only PDF and DOCX files are supported.'); return; }
  if (file.size > 10 * 1024 * 1024) { showStatus('error', '⚠️ File exceeds the 10 MB limit.'); return; }
  selectedFile = file;
  uploadTitle.textContent = `📎 ${file.name} (${formatBytes(file.size)})`;
  uploadZone.classList.add('ls-upload-zone--has-file');
  extractBtn.disabled = false;
  clearStatus();
}

// ── Submit ────────────────────────────────────────────────────
extractBtn.addEventListener('click', async () => {
  if (!selectedFile) return;
  const token = localStorage.getItem('access_token');
  if (!token) { window.location.href = '/login'; return; }

  setLoading(true);
  clearStatus();
  resultsSection.style.display = 'none';

  const formData = new FormData();
  formData.append('file', selectedFile);

  try {
    const res = await fetch('/api/extract', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    if (res.status === 401) { window.location.href = '/login'; return; }
    const data = await res.json();
    if (!res.ok) { showStatus('error', `❌ ${data.msg || 'Extraction failed. Please try again.'}`); return; }
    allClauses = data.clauses || [];
    renderResults(data.document_id);
    showStatus('success', `✅ Found ${allClauses.length} clause${allClauses.length !== 1 ? 's' : ''} in your document.`);
  } catch (err) {
    showStatus('error', '❌ Could not connect to the server. Please try again.');
    console.error(err);
  } finally {
    setLoading(false);
  }
});

// ── Render all results ────────────────────────────────────────
function renderResults(docId) {
  docIdBadge.textContent = `doc: ${(docId || '').slice(0, 8)}…`;
  clauseCount.textContent = allClauses.length;

  // Stats bar — count per clause type
  const typeCounts = {};
  allClauses.forEach(c => { typeCounts[c.clause_type] = (typeCounts[c.clause_type] || 0) + 1; });

  statsBar.innerHTML = Object.entries(typeCounts).map(([type, cnt]) => {
    const meta = CLAUSE_META[type] || { emoji: '📄', label: type };
    return `<div class="ls-stat">
      <div class="ls-stat__label">${meta.emoji} ${meta.label}</div>
      <div class="ls-stat__value">${cnt}</div>
    </div>`;
  }).join('');

  // Legend
  const seenTypes = [...new Set(allClauses.map(c => c.clause_type))];
  clauseLegend.innerHTML = seenTypes.map(type => {
    const meta = CLAUSE_META[type] || { label: type, color: '#888' };
    return `<div class="legend-item">
      <span class="legend-dot" style="background:${meta.color}"></span>
      ${meta.label}
    </div>`;
  }).join('');

  // Filter bar chips (rebuild)
  // Keep the "All" chip, add one per type
  const existing = filterBar.querySelectorAll('[data-filter]:not([data-filter="ALL"])');
  existing.forEach(el => el.remove());
  seenTypes.forEach(type => {
    const meta = CLAUSE_META[type] || { emoji: '📄', label: type };
    const btn = document.createElement('button');
    btn.className = 'filter-chip';
    btn.dataset.filter = type;
    btn.textContent = `${meta.emoji} ${meta.label}`;
    btn.addEventListener('click', () => applyFilter(type));
    filterBar.appendChild(btn);
  });

  // Reset filter to ALL
  activeFilter = 'ALL';
  document.getElementById('filterAll').classList.add('filter-chip--all');
  applyFilter('ALL', false); // render without re-scrolling

  resultsSection.style.display = 'block';
  resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── Filter & render clause cards ──────────────────────────────
document.getElementById('filterAll').addEventListener('click', () => applyFilter('ALL'));

function applyFilter(filter, scroll = true) {
  activeFilter = filter;

  // Update chip styles
  filterBar.querySelectorAll('[data-filter]').forEach(btn => {
    const isAll = btn.dataset.filter === 'ALL';
    const isActive = btn.dataset.filter === filter;
    btn.classList.toggle('filter-chip--active', isActive && !isAll);
    btn.classList.toggle('filter-chip--all', isAll && filter === 'ALL');
    if (isAll) btn.style.background = filter === 'ALL' ? 'var(--text)' : '';
  });

  const filtered = filter === 'ALL' ? allClauses : allClauses.filter(c => c.clause_type === filter);
  renderClauseCards(filtered);
}

function renderClauseCards(clauses) {
  clausesList.innerHTML = '';

  if (!clauses.length) {
    clausesList.innerHTML = `
      <div class="ls-empty">
        <span class="ls-empty__icon">🔎</span>
        <div class="ls-empty__title">No clauses found</div>
        <div class="ls-empty__hint">Try a different filter or upload a different document.</div>
      </div>`;
    return;
  }

  clauses.forEach((clause, i) => {
    const meta = CLAUSE_META[clause.clause_type] || { emoji: '📄', label: clause.clause_type };
    const pct  = Math.round((clause.confidence || 0) * 100);
    const card = document.createElement('div');
    card.className = `ls-clause-card ls-clause-card--${clause.clause_type} ls-fade-in`;
    card.style.animationDelay = `${Math.min(i * 50, 400)}ms`;
    card.innerHTML = `
      <div class="ls-clause-card__header">
        <span class="ls-clause-chip ls-clause-chip--${clause.clause_type}">
          ${meta.emoji} ${meta.label}
        </span>
        <span class="ls-clause-card__confidence">Confidence: ${pct}%</span>
      </div>
      <div class="ls-clause-card__text">${escapeHtml(clause.clause_text)}</div>
      <div class="ls-confidence-bar">
        <div class="ls-confidence-bar__fill"
             style="width:${pct}%; background:${CLAUSE_META[clause.clause_type]?.color || '#888'}">
        </div>
      </div>`;
    clausesList.appendChild(card);
  });
}

// ── Helpers ───────────────────────────────────────────────────
function setLoading(on) {
  extractBtn.disabled = on;
  btnIcon.innerHTML = on ? '<span class="ls-spinner"></span>' : '🔍';
  btnLabel.textContent = on ? 'Extracting… this may take a moment' : 'Extract Clauses';
}
function showStatus(type, msg) { statusMsg.innerHTML = `<div class="ls-alert ls-alert--${type}">${msg}</div>`; }
function clearStatus() { statusMsg.innerHTML = ''; }
function formatBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
  return (b / 1048576).toFixed(1) + ' MB';
}
function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str ?? '';
  return d.innerHTML;
}
