/* Fetch captions in the user's browser (home IP), not from Render's blocked cloud IP. */

const INVIDIOUS_INSTANCES = [
  'https://invidious.private.coffee',
  'https://inv.tux.pizza',
  'https://invidious.fdn.fr',
];

function extractVideoIdFromUrl(url) {
  const patterns = [
    /(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([A-Za-z0-9_-]{11})/,
    /^([A-Za-z0-9_-]{11})$/,
  ];
  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (match) return match[1];
  }
  return null;
}

function parseVttTime(value) {
  const clean = value.trim().split(/\s+/)[0].replace(',', '.');
  const parts = clean.split(':').map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0] || 0;
}

function parseVtt(vttText) {
  const segments = [];
  const lines = vttText.replace(/\r\n/g, '\n').split('\n');
  let i = 0;

  while (i < lines.length) {
    const line = lines[i].trim();
    if (line.includes('-->')) {
      const [startStr, endStr] = line.split('-->').map(s => s.trim());
      const start = parseVttTime(startStr);
      const end = parseVttTime(endStr);
      i += 1;
      const textLines = [];

      while (i < lines.length) {
        const chunk = lines[i].trim();
        if (!chunk) break;
        if (chunk.includes('-->') && /[\d:.]/.test(chunk)) break;
        if (/^\d+$/.test(chunk)) { i += 1; continue; }
        textLines.push(chunk.replace(/<[^>]+>/g, ''));
        i += 1;
      }

      const text = textLines.join(' ').trim();
      if (text) {
        segments.push({ text, start, duration: Math.max(0, end - start) });
      }
      continue;
    }
    i += 1;
  }

  return segments;
}

function parseJson3Transcript(jsonText) {
  const data = JSON.parse(jsonText);
  const segments = [];
  for (const event of data.events || []) {
    if (!event.segs) continue;
    const text = event.segs.map(s => s.utf8 || '').join('').trim();
    if (!text || text === '\n') continue;
    segments.push({
      text,
      start: (event.tStartMs || 0) / 1000,
      duration: (event.dDurationMs || 0) / 1000,
    });
  }
  return segments;
}

function segmentsToPayload(segments) {
  const fullText = segments.map(s => s.text).join(' ').replace(/\s+/g, ' ').trim();
  const last = segments[segments.length - 1];
  return {
    full_text: fullText,
    word_count: fullText.split(/\s+/).filter(Boolean).length,
    duration_seconds: Math.floor((last.start || 0) + (last.duration || 0)),
  };
}

async function fetchViaCorsProxy(targetUrl) {
  const builders = [
    (u) => `https://api.allorigins.win/raw?url=${encodeURIComponent(u)}`,
    (u) => `https://corsproxy.io/?${encodeURIComponent(u)}`,
  ];

  for (const build of builders) {
    try {
      const res = await fetch(build(targetUrl));
      if (!res.ok) continue;
      const text = await res.text();
      if (text && text.trim()) return text;
    } catch (_) {
      /* try next proxy */
    }
  }
  return null;
}

function pickCaptionLang(listXml) {
  const langs = [...listXml.matchAll(/lang_code="([^"]+)"/g)].map(m => m[1]);
  if (!langs.length) return 'en';
  if (langs.includes('en')) return 'en';
  if (langs.includes('a.en')) return 'a.en';
  return langs[0];
}

async function fetchTranscriptViaTimedText(videoId) {
  const listUrl = `https://www.youtube.com/api/timedtext?type=list&v=${videoId}`;
  const listXml = await fetchViaCorsProxy(listUrl);
  if (!listXml || !listXml.includes('lang_code')) return null;

  const lang = pickCaptionLang(listXml);
  const attempts = [
    `https://www.youtube.com/api/timedtext?v=${videoId}&lang=${lang}&fmt=json3`,
    `https://www.youtube.com/api/timedtext?v=${videoId}&lang=${lang}&fmt=json3&kind=asr`,
    `https://www.youtube.com/api/timedtext?v=${videoId}&lang=en&fmt=json3&kind=asr`,
  ];

  for (const url of attempts) {
    const jsonText = await fetchViaCorsProxy(url);
    if (!jsonText || jsonText.length < 20) continue;
    try {
      const segments = parseJson3Transcript(jsonText);
      if (segments.length) return segmentsToPayload(segments);
    } catch (_) {
      /* try next URL */
    }
  }
  return null;
}

async function fetchTranscriptViaInvidious(videoId) {
  for (const base of INVIDIOUS_INSTANCES) {
    try {
      const directUrl = `${base}/api/v1/captions/${videoId}?lang=en`;
      const directRes = await fetch(directUrl);
      if (directRes.ok) {
        const segments = parseVtt(await directRes.text());
        if (segments.length) return segmentsToPayload(segments);
      }

      const listRes = await fetch(`${base}/api/v1/captions/${videoId}`);
      if (!listRes.ok) continue;

      const data = await listRes.json();
      const captions = data.captions || [];
      if (!captions.length) continue;

      let chosen = captions.find(c => (c.languageCode || '').toLowerCase().startsWith('en'));
      chosen = chosen || captions[0];

      let captionUrl = chosen.url || '';
      if (captionUrl.startsWith('/')) captionUrl = base.replace(/\/$/, '') + captionUrl;

      const capRes = await fetch(`${captionUrl}${captionUrl.includes('?') ? '&' : '?'}lang=en`);
      if (!capRes.ok) continue;

      const segments = parseVtt(await capRes.text());
      if (segments.length) return segmentsToPayload(segments);
    } catch (_) {
      /* try next instance */
    }
  }
  return null;
}

async function fetchTranscriptInBrowser(videoId) {
  const timed = await fetchTranscriptViaTimedText(videoId);
  if (timed) return timed;
  return fetchTranscriptViaInvidious(videoId);
}
