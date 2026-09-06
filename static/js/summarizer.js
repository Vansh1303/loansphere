/**
 * LoanSphere — Summarizer JS
 * Handles file upload, mode toggle, API call and card rendering
 */

const uploadZone     = document.getElementById('uploadZone');
const fileInput      = document.getElementById('fileInput');
const uploadTitle    = document.getElementById('uploadTitle');
const summaryModeEl  = document.getElementById('summaryMode');
const summarizeBtn   = document.getElementById('summarizeBtn');
const btnIcon        = document.getElementById('btnIcon');
const btnLabel       = document.getElementById('btnLabel');
const statusMsg      = document.getElementById('statusMsg');
const resultsSection = document.getElementById('resultsSection');
const cardsGrid      = document.getElementById('cardsGrid');
const docIdBadge     = document.getElementById('docIdBadge');

let selectedFile = null;

// Mode toggle
document.getElementById('btnBrief').addEventListener('click', () => setMode('brief'));
document.getElementById('btnDetailed').addEventListener('click', () => setMode('detailed'));

function setMode(mode) {
  summaryModeEl.value = mode;
  document.getElementById('btnBrief').classList.toggle('ls-toggle__btn--active', mode === 'brief');
  document.getElementById('btnDetailed').classList.toggle('ls-toggle__btn--active', mode === 'detailed');
}

// Drag & drop
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
  if (file.size > 10 * 1024 * 1024) { showStatus('error', '⚠️ File is too large. Maximum size is 10 MB.'); return; }
  selectedFile = file;
  uploadTitle.textContent = `📎 ${file.name} (${formatBytes(file.size)})`;
  uploadZone.classList.add('ls-upload-zone--has-file');
  summarizeBtn.disabled = false;
  clearStatus();
}

// Submit
summarizeBtn.addEventListener('click', async () => {
  if (!selectedFile) return;
  const token = localStorage.getItem('access_token');
  if (!token) { window.location.href = '/login'; return; }

  setLoading(true);
  clearStatus();
  resultsSection.style.display = 'none';

  const formData = new FormData();
  formData.append('file', selectedFile);
  formData.append('summary_mode', summaryModeEl.value);

  try {
    const res = await fetch('/api/summarize', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    if (res.status === 401) { window.location.href = '/login'; return; }
    const data = await res.json();
    if (!res.ok) { showStatus('error', `❌ ${data.msg || 'Summarization failed.'}`); return; }
    renderResults(data);
    showStatus('success', `✅ Summary ready — ${summaryModeEl.value} mode.`);
  } catch (err) {
    showStatus('error', '❌ Could not connect to the server. Please try again.');
    console.error(err);
  } finally {
    setLoading(false);
  }
});

// Render results
function renderResults(data) {
  cardsGrid.innerHTML = '';
  docIdBadge.textContent = `doc: ${(data.document_id || '').slice(0, 8)}…`;
  const cards = data.cards || [];
  if (!cards.length) {
    cardsGrid.innerHTML = '<p style="color:var(--text-muted)">No summary data returned.</p>';
    resultsSection.style.display = 'block';
    return;
  }
  cards.forEach((card, i) => {
    const isWide = i === 0; // Document Summary spans full width
    const el = document.createElement('div');
    el.className = `ls-summary-card${isWide ? ' doc-summary-section' : ''} ls-fade-in`;
    el.style.animationDelay = `${i * 60}ms`;
    el.innerHTML = `<div class="ls-summary-card__label">${escapeHtml(card.label)}</div>
                    <div class="ls-summary-card__value">${escapeHtml(card.value)}</div>`;
    cardsGrid.appendChild(el);
  });
  resultsSection.style.display = 'block';
  resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Helpers
function setLoading(on) {
  summarizeBtn.disabled = on;
  btnIcon.innerHTML = on ? '<span class="ls-spinner"></span>' : '✨';
  btnLabel.textContent = on ? 'Summarizing… this may take a moment' : 'Summarize Document';
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
  d.textContent = str ?? 'N/A';
  return d.innerHTML;
}
