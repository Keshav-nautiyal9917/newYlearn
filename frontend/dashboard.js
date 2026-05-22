/* ============================================================
   dashboard.js  — Dashboard page logic + AI Chat
   (API_BASE, getState, saveState, showLoading, hideLoading,
    showToast, escapeHtml, fmtDur are all provided by app.js)
   ============================================================ */

let chatHistory = [];       // { role: 'user'|'ai', content: string }
let chatTranscript = '';    // cached transcript for chat API calls

// ─── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  const state = getState();
  if (!state.transcript) {
    window.location.href = '/';
    return;
  }

  chatTranscript = state.transcript;

  // ── Sidebar video card ────────────────────────────────────
  const vid = state.video_id;
  const thumb = state.thumbnail || `https://img.youtube.com/vi/${vid}/mqdefault.jpg`;

  document.getElementById('side-thumb').src = thumb;
  document.getElementById('side-title').textContent = state.video_title || 'YouTube Video';
  document.getElementById('side-meta').textContent = fmtDur(state.duration_seconds);

  // ── Dashboard banner ──────────────────────────────────────
  const dbThumb = document.getElementById('db-thumb');
  dbThumb.src = thumb;
  dbThumb.onerror = () => { dbThumb.src = `https://img.youtube.com/vi/${vid}/mqdefault.jpg`; };
  document.getElementById('db-title').textContent = state.video_title || 'YouTube Video';
  document.getElementById('db-meta').innerHTML = `
    <span class="badge badge-purple">📝 ${(state.word_count || 0).toLocaleString()} words</span>
    <span class="badge badge-blue">⏱ ${fmtDur(state.duration_seconds)}</span>
    <span class="badge badge-green">✅ Transcript ready</span>
  `;

  // ── YouTube link ──────────────────────────────────────────
  document.getElementById('yt-link').href = `https://www.youtube.com/watch?v=${vid}`;

  // ── Load or fetch notes ───────────────────────────────────
  if (state.notes_data) {
    renderDashboardNotes(state.notes_data);
  } else {
    fetchAndRenderNotes(state.transcript, state.video_title);
  }
});

// ─── Tab Switching ────────────────────────────────────────────────────────────

function switchDashTab(name) {
  document.querySelectorAll('.dash-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.dash-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('dtab-' + name).classList.add('active');
  document.getElementById('dpanel-' + name).classList.add('active');
}

// ─── Fetch Notes from API ─────────────────────────────────────────────────────

async function fetchAndRenderNotes(transcript, title) {
  showLoading('Generating AI notes & summary…');
  try {
    const res = await fetch(`${API_BASE}/api/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transcript, video_title: title }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'AI generation failed.');
    const data = await res.json();
    saveState({ notes_data: data });
    renderDashboardNotes(data);
  } catch (e) {
    showToast('error', '❌ ' + e.message);
    document.getElementById('db-summary-content').innerHTML =
      `<p style="color:var(--danger)">Failed to load. <a href="#" onclick="location.reload()" style="color:var(--accent-2)">Retry</a></p>`;
  } finally {
    hideLoading();
  }
}

// ─── Render Notes Data ────────────────────────────────────────────────────────

function renderDashboardNotes(data) {
  // Summary
  const sumEl = document.getElementById('db-summary-content');
  sumEl.innerHTML = data.summary
    ? data.summary.split('\n').filter(Boolean)
        .map(p => `<p class="summary-text">${escapeHtml(p)}</p>`).join('')
    : '<p class="summary-text" style="color:var(--text-muted)">No summary available.</p>';

  // Notes
  const notesEl = document.getElementById('db-notes-content');
  if (data.notes && data.notes.length) {
    notesEl.innerHTML = data.notes.map(section => `
      <div class="notes-section">
        <div class="notes-topic">${escapeHtml(section.topic)}</div>
        <ul class="notes-list">
          ${(section.points || []).map(p => `<li>${escapeHtml(p)}</li>`).join('')}
        </ul>
      </div>
    `).join('');
  } else {
    notesEl.innerHTML = '<p style="color:var(--text-muted)">No notes generated.</p>';
  }

  // Glossary
  const glossEl = document.getElementById('db-glossary-content');
  if (data.glossary && data.glossary.length) {
    glossEl.innerHTML = `<div class="glossary-grid">
      ${data.glossary.map(g => `
        <div class="glossary-card">
          <div class="glossary-term">${escapeHtml(g.term)}</div>
          <div class="glossary-def">${escapeHtml(g.definition)}</div>
        </div>
      `).join('')}
    </div>`;
  } else {
    glossEl.innerHTML = '<p style="color:var(--text-muted)">No glossary generated.</p>';
  }
}

// ─── Sidebar Toggle (mobile) ──────────────────────────────────────────────────

function toggleSidebar() {
  document.getElementById('left-sidebar').classList.toggle('open');
}

// ─── Chat Sidebar ─────────────────────────────────────────────────────────────

let chatOpen = true;

function toggleChat() {
  const sidebar = document.getElementById('chat-sidebar');
  const fab = document.getElementById('chat-fab');

  if (window.innerWidth <= 768) {
    // Mobile: slide in/out
    sidebar.classList.toggle('mobile-open');
    chatOpen = sidebar.classList.contains('mobile-open');
  } else {
    // Desktop: collapse width
    chatOpen = !chatOpen;
    sidebar.classList.toggle('hidden', !chatOpen);
  }

  fab.classList.toggle('visible', !chatOpen);
}

// ─── Send Chat Message ────────────────────────────────────────────────────────

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const question = input.value.trim();
  if (!question) return;

  input.value = '';
  input.style.height = 'auto';

  // Append user bubble
  appendChatBubble('user', question);
  chatHistory.push({ role: 'user', content: question });

  // Typing indicator
  const typingId = appendTypingIndicator();

  const sendBtn = document.getElementById('chat-send-btn');
  sendBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transcript: chatTranscript,
        question: question,
        history: chatHistory.slice(-10), // last 10 turns
      }),
    });

    removeTypingIndicator(typingId);

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'AI chat failed.');
    }

    const data = await res.json();
    const aiReply = data.response || 'I could not generate a response.';

    appendChatBubble('ai', aiReply);
    chatHistory.push({ role: 'ai', content: aiReply });

  } catch (e) {
    removeTypingIndicator(typingId);
    appendChatBubble('ai', `⚠️ Error: ${e.message}`);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function handleChatKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendChatMessage();
  }
}

// ─── Chat UI Helpers ──────────────────────────────────────────────────────────

function appendChatBubble(role, text) {
  const container = document.getElementById('chat-messages');
  const isUser = role === 'user';

  const div = document.createElement('div');
  div.className = `chat-bubble ${isUser ? 'user' : 'ai'}`;

  // Simple markdown: **bold**, *italic*, newlines → <br>
  const formatted = text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>');

  div.innerHTML = `
    <div class="bubble-avatar">${isUser ? '👤' : '🤖'}</div>
    <div class="bubble-text">${formatted}</div>
  `;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return div;
}

function appendTypingIndicator() {
  const container = document.getElementById('chat-messages');
  const id = 'typing-' + Date.now();
  const div = document.createElement('div');
  div.className = 'chat-bubble ai';
  div.id = id;
  div.innerHTML = `
    <div class="bubble-avatar">🤖</div>
    <div class="bubble-text typing" style="color:var(--text-muted);font-style:italic">Thinking</div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return id;
}

function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}
