/* ============================================================
   app.js  —  Shared frontend logic for YLearn
   ============================================================ */

const API_BASE = '';  // Netlify proxies /api/* → Render backend (no CORS needed)


function getState() {
  try {
    return JSON.parse(sessionStorage.getItem('ylearnState') || '{}');
  } catch { return {}; }
}

function saveState(patch) {
  const current = getState();
  sessionStorage.setItem('ylearnState', JSON.stringify({ ...current, ...patch }));
}

function clearState() {
  sessionStorage.removeItem('ylearnState');
}

// ─── Loading Overlay ──────────────────────────────────────────────────────────

function showLoading(msg = 'Processing…') {
  const el = document.getElementById('loading');
  const msgEl = document.getElementById('loading-msg');
  if (el) el.classList.add('active');
  if (msgEl) msgEl.textContent = msg;
}

function hideLoading() {
  const el = document.getElementById('loading');
  if (el) el.classList.remove('active');
}

// ─── Toast Notifications ──────────────────────────────────────────────────────

function showToast(type, message, duration = 4000) {
  const container = document.getElementById('toasts');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'none';
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ─── Utility ──────────────────────────────────────────────────────────────────

function escapeHtml(text) {
  if (typeof text !== 'string') return String(text ?? '');
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function fmtDur(seconds) {
  if (!seconds) return '—';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

// ─── Navigation helpers ───────────────────────────────────────────────────────

function goToNotes() {
  window.location.href = './dashboard.html';
}

function goToDashboard() {
  window.location.href = './dashboard.html';
}

function goToQuiz() {
  window.location.href = './quiz.html';
}

// ─── Home Page: Process Video ─────────────────────────────────────────────────

async function processVideo() {
  const urlInput = document.getElementById('youtube-url');
  const url = urlInput ? urlInput.value.trim() : '';

  if (!url) {
    showToast('error', '⚠️ Please enter a YouTube URL first.');
    return;
  }

  const btn = document.getElementById('process-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Fetching…'; }

  showLoading('Fetching video transcript…');
  clearState();

  try {
    const videoId = typeof extractVideoIdFromUrl === 'function'
      ? extractVideoIdFromUrl(url)
      : null;

    const body = { url };
    const onCloudHost = /\.onrender\.com$|\.railway\.app$|\.vercel\.app$/i.test(window.location.hostname);

    // Local only: try browser captions (skipped on Render — proxies fail with 403/502).
    if (!onCloudHost && videoId && typeof fetchTranscriptInBrowser === 'function') {
      showLoading('Fetching captions…');
      const clientPayload = await fetchTranscriptInBrowser(videoId);
      if (clientPayload) {
        Object.assign(body, {
          video_id: videoId,
          transcript: clientPayload.full_text,
          word_count: clientPayload.word_count,
          duration_seconds: clientPayload.duration_seconds,
        });
      }
    }

    showLoading(
      body.transcript
        ? 'Saving transcript…'
        : 'AI is reading the video (30–90 sec on Render)…'
    );

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120000);

    const res = await fetch(`${API_BASE}/api/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      let errorMsg = 'Failed to process video.';
      try {
        const errorData = await res.json();
        errorMsg = errorData.detail || errorMsg;
      } catch (e) {
        if (res.status === 504 || res.status === 502) {
          errorMsg = 'The AI server is waking up from sleep. Please wait 30 seconds and try again.';
        } else {
          errorMsg = `Server error (${res.status}). Please try again.`;
        }
      }
      throw new Error(errorMsg);
    }

    const data = await res.json();

    // Persist to session state
    saveState({
      video_id:        data.video_id,
      video_title:     data.video_title,
      thumbnail:       data.thumbnail,
      transcript:      data.transcript,
      word_count:      data.word_count,
      duration_seconds: data.duration_seconds,
    });

    // Show preview card
    const preview = document.getElementById('video-preview');
    const thumbImg = document.getElementById('thumb-img');
    const thumbTitle = document.getElementById('thumb-title');
    const thumbWords = document.getElementById('thumb-words');
    const thumbDur   = document.getElementById('thumb-dur');

    if (preview) {
      thumbImg.src   = data.thumbnail;
      thumbImg.onerror = () => { thumbImg.src = `https://img.youtube.com/vi/${data.video_id}/mqdefault.jpg`; };
      thumbTitle.textContent = data.video_title || 'YouTube Video';
      thumbWords.textContent = `${(data.word_count || 0).toLocaleString()} words`;
      thumbDur.textContent   = fmtDur(data.duration_seconds);
      preview.style.display  = 'block';
      preview.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    showToast('success', '✅ Transcript fetched! Choose an option below.');

  } catch (err) {
    const msg = err.name === 'AbortError'
      ? 'Request timed out. Try a shorter video or wait and retry.'
      : err.message;
    showToast('error', `❌ ${msg}`);
  } finally {
    hideLoading();
    if (btn) { btn.disabled = false; btn.innerHTML = '▶ Analyse Video'; }
  }
}

// Allow pressing Enter in URL input
document.addEventListener('DOMContentLoaded', () => {
  const urlInput = document.getElementById('youtube-url');
  if (urlInput) {
    urlInput.addEventListener('keydown', e => {
      if (e.key === 'Enter') processVideo();
    });
  }
});
