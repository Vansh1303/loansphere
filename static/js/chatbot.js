/**
 * chatbot.js — LoanSphere Document Q&A Chatbot
 * Flow:
 *  1. User uploads PDF/DOCX → POST /api/extract  → get document_id
 *  2. Auto-create session   → POST /api/chat/session → get session_id
 *  3. User sends messages   → POST /api/chat → get answer + cited_clause
 */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
let documentId  = null;
let sessionId   = null;
let isWaiting   = false;

// Generate a client-side session ID (used as fallback / correlation only)
const clientSessionId = crypto.randomUUID();

// ── DOM refs ──────────────────────────────────────────────────────────────────
const fileInput     = document.getElementById('fileInput');
const uploadZone    = document.getElementById('uploadZone');
const uploadTitle   = document.getElementById('uploadTitle');
const uploadStatus  = document.getElementById('uploadStatus');
const docInfo       = document.getElementById('docInfo');
const docName       = document.getElementById('docName');
const promptCard    = document.getElementById('promptCard');
const uploadHint    = document.getElementById('uploadHint');

const chatMessages  = document.getElementById('chatMessages');
const chatEmpty     = document.getElementById('chatEmpty');
const chatInput     = document.getElementById('chatInput');
const sendBtn       = document.getElementById('sendBtn');
const statusDot     = document.getElementById('statusDot');
const statusLabel   = document.getElementById('statusLabel');

// ── Auth helper ───────────────────────────────────────────────────────────────
function getToken() {
  return localStorage.getItem('access_token') || '';
}

function authHeaders(json = false) {
  const h = { Authorization: `Bearer ${getToken()}` };
  if (json) h['Content-Type'] = 'application/json';
  return h;
}

// ── Status dot ────────────────────────────────────────────────────────────────
function setStatus(state) {
  statusDot.className = 'status-dot';
  if (state === 'active') {
    statusDot.classList.add('status-dot--active');
    statusLabel.textContent = 'Ready';
    statusLabel.style.color = 'var(--success)';
  } else if (state === 'thinking') {
    statusDot.classList.add('status-dot--thinking');
    statusLabel.textContent = 'Thinking…';
    statusLabel.style.color = 'var(--warning)';
  } else {
    statusLabel.textContent = 'Idle';
    statusLabel.style.color = 'var(--text-muted)';
  }
}

// ── Upload zone drag-and-drop ─────────────────────────────────────────────────
uploadZone.addEventListener('dragover', e => {
  e.preventDefault();
  uploadZone.classList.add('ls-upload-zone--drag');
});
['dragleave', 'drop'].forEach(evt =>
  uploadZone.addEventListener(evt, () => uploadZone.classList.remove('ls-upload-zone--drag'))
);
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  const file = e.dataTransfer?.files?.[0];
  if (file) handleFile(file);
});
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

// ── Upload & session creation ─────────────────────────────────────────────────
async function handleFile(file) {
  const validTypes = ['application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
  if (!validTypes.includes(file.type) && !/\.(pdf|docx?)$/i.test(file.name)) {
    showUploadStatus('error', '❌ Please upload a PDF or DOCX file.');
    return;
  }

  // Reset state
  documentId = null;
  sessionId  = null;
  disableChat();

  uploadZone.classList.remove('ls-upload-zone--has-file');
  uploadTitle.textContent = 'Uploading…';
  showUploadStatus('info', '⏳ Uploading document…');

  // 1️⃣  Extract / upload document
  const formData = new FormData();
  formData.append('file', file);

  let extractData;
  try {
    const res = await fetch('/api/extract', {
      method: 'POST',
      headers: { Authorization: `Bearer ${getToken()}` },
      body: formData,
    });
    extractData = await res.json();
    if (!res.ok) throw new Error(extractData.msg || `HTTP ${res.status}`);
  } catch (err) {
    uploadTitle.textContent = 'Upload failed';
    showUploadStatus('error', `❌ Upload failed: ${err.message}`);
    return;
  }

  documentId = extractData.document_id;
  if (!documentId) {
    showUploadStatus('error', '❌ Server did not return a document_id.');
    return;
  }

  showUploadStatus('info', '🔗 Creating chat session…');

  // 2️⃣  Create chat session
  let sessionData;
  try {
    const res = await fetch('/api/chat/session', {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({ document_id: documentId }),
    });
    sessionData = await res.json();
    if (!res.ok) throw new Error(sessionData.msg || `HTTP ${res.status}`);
  } catch (err) {
    showUploadStatus('error', `❌ Session creation failed: ${err.message}`);
    return;
  }

  sessionId = sessionData.session_id;
  if (!sessionId) {
    showUploadStatus('error', '❌ Server did not return a session_id.');
    return;
  }

  // ✅ Both IDs ready — activate chat
  uploadZone.classList.add('ls-upload-zone--has-file');
  uploadTitle.textContent = file.name;
  docName.textContent = file.name;
  docInfo.style.display = 'flex';
  promptCard.style.display = 'block';
  uploadHint.style.display = 'none';
  showUploadStatus('success', '✅ Document ready — start chatting below!');

  enableChat();
  setStatus('active');

  // Remove empty state and show welcome bubble
  chatEmpty.style.display = 'none';
  appendBotMessage(
    'Document loaded! I\'m ready to answer questions about your loan agreement. What would you like to know?',
    null
  );
}

// ── Chat enable/disable ───────────────────────────────────────────────────────
function enableChat() {
  chatInput.disabled = false;
  sendBtn.disabled   = false;
  chatInput.placeholder = 'Ask a question about your document…';
  chatInput.focus();
}

function disableChat() {
  chatInput.disabled = true;
  sendBtn.disabled   = true;
  chatInput.placeholder = 'Upload a document to start chatting…';
}

// ── Sending messages ──────────────────────────────────────────────────────────
sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Auto-resize textarea
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 110) + 'px';
});

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || isWaiting || !sessionId || !documentId) return;

  isWaiting = true;
  chatInput.value = '';
  chatInput.style.height = 'auto';
  sendBtn.disabled = true;
  setStatus('thinking');

  // Show user bubble
  appendUserMessage(text);

  // Show typing indicator
  const typingId = showTyping();

  let data;
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({
        session_id: sessionId,
        document_id: documentId,
        message: text,
      }),
    });
    data = await res.json();
    if (!res.ok) throw new Error(data.msg || `HTTP ${res.status}`);
  } catch (err) {
    removeTyping(typingId);
    appendBotMessage(`⚠️ Error: ${err.message}`, null);
    isWaiting = false;
    sendBtn.disabled = false;
    setStatus('active');
    return;
  }

  removeTyping(typingId);
  appendBotMessage(data.answer, data.cited_clause || null);

  isWaiting = false;
  sendBtn.disabled = false;
  setStatus('active');
  chatInput.focus();
}

// ── Message rendering ─────────────────────────────────────────────────────────
function appendUserMessage(text) {
  chatEmpty.style.display = 'none';

  const row = document.createElement('div');
  row.className = 'bubble-row bubble-row--user';
  row.innerHTML = `
    <div class="bubble-content">
      <div class="bubble bubble--user">${escapeHtml(text)}</div>
    </div>
    <div class="bubble-avatar bubble-avatar--user">👤</div>`;
  chatMessages.appendChild(row);
  scrollToBottom();
}

function appendBotMessage(text, citedClause) {
  chatEmpty.style.display = 'none';

  const citationHtml = citedClause
    ? `<div class="bubble-citation">
         <span class="bubble-citation__dot"></span>
         Clause: ${escapeHtml(citedClause)}
       </div>`
    : '';

  const row = document.createElement('div');
  row.className = 'bubble-row bubble-row--bot';
  row.innerHTML = `
    <div class="bubble-avatar bubble-avatar--bot">🤖</div>
    <div class="bubble-content">
      <div class="bubble bubble--bot">${escapeHtml(text)}</div>
      ${citationHtml}
    </div>`;
  chatMessages.appendChild(row);
  scrollToBottom();
}

// ── Typing indicator ──────────────────────────────────────────────────────────
function showTyping() {
  const id = 'typing-' + Date.now();
  const row = document.createElement('div');
  row.className = 'bubble-row bubble-row--bot';
  row.id = id;
  row.innerHTML = `
    <div class="bubble-avatar bubble-avatar--bot">🤖</div>
    <div class="bubble-content">
      <div class="typing-indicator">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </div>
    </div>`;
  chatMessages.appendChild(row);
  scrollToBottom();
  return id;
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ── Suggested prompts ─────────────────────────────────────────────────────────
window.usePrompt = function(btn) {
  if (!sessionId) return;
  chatInput.value = btn.textContent;
  chatInput.dispatchEvent(new Event('input'));
  sendMessage();
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '<br>');
}

function showUploadStatus(type, msg) {
  const icons = { info: 'ls-alert--info', success: 'ls-alert--success', error: 'ls-alert--error' };
  uploadStatus.innerHTML = `<div class="ls-alert ${icons[type] || ''}">${msg}</div>`;
}
