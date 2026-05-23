import os
import re
import httpx
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)

# Invidious mirrors captions without hitting YouTube from a datacenter IP directly.
INVIDIOUS_INSTANCES = [
    "https://vid.puffyan.us",
    "https://inv.nadeau.net",
    "https://invidious.privacydev.net",
    "https://invidious.fdn.fr",
]


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _create_youtube_api() -> YouTubeTranscriptApi:
    username = os.getenv("WEBSHARE_PROXY_USERNAME", "").strip()
    password = os.getenv("WEBSHARE_PROXY_PASSWORD", "").strip()
    if username and password:
        try:
            from youtube_transcript_api.proxies import WebshareProxyConfig

            return YouTubeTranscriptApi(
                proxy_config=WebshareProxyConfig(
                    proxy_username=username,
                    proxy_password=password,
                )
            )
        except ImportError:
            pass
    return YouTubeTranscriptApi()


def _is_ip_block_error(message: str) -> bool:
    lower = message.lower()
    return any(
        token in lower
        for token in (
            "blocking requests from your ip",
            "ipblocked",
            "requestblocked",
            "cloud provider",
            "too many requests",
        )
    )


def _snippet_to_dict(snippet) -> dict:
    """Normalise a FetchedTranscriptSnippet (v1.x) or plain dict (v0.x) to dict."""
    if isinstance(snippet, dict):
        return snippet
    return {
        "text": snippet.text,
        "start": snippet.start,
        "duration": snippet.duration,
    }


def _parse_vtt_time(value: str) -> float:
    value = value.strip().split()[0]
    parts = value.replace(",", ".").split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(parts[0])


def _parse_vtt(vtt_text: str) -> list[dict]:
    segments: list[dict] = []
    lines = vtt_text.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            start_str, end_str = [p.strip() for p in line.split("-->", 1)]
            start = _parse_vtt_time(start_str)
            end = _parse_vtt_time(end_str)
            i += 1
            text_lines: list[str] = []
            while i < len(lines):
                chunk = lines[i].strip()
                if not chunk:
                    break
                if "-->" in chunk and re.match(r"[\d:.]+", chunk):
                    break
                if chunk.isdigit():
                    i += 1
                    continue
                text_lines.append(re.sub(r"<[^>]+>", "", chunk))
                i += 1
            text = " ".join(text_lines).strip()
            if text:
                segments.append(
                    {"text": text, "start": start, "duration": max(0.0, end - start)}
                )
            continue
        i += 1
    return segments


def _segments_to_result(video_id: str, segments: list[dict]) -> dict:
    if not segments:
        raise ValueError("Transcript returned no content for this video.")

    full_text = " ".join(seg["text"] for seg in segments)
    last = segments[-1]
    duration_seconds = int(last["start"] + last["duration"])

    return {
        "video_id": video_id,
        "full_text": full_text,
        "segments": segments,
        "word_count": len(full_text.split()),
        "duration_seconds": duration_seconds,
    }


def _fetch_via_invidious(video_id: str) -> list[dict]:
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        for base in INVIDIOUS_INSTANCES:
            try:
                direct = client.get(
                    f"{base}/api/v1/captions/{video_id}",
                    params={"lang": "en"},
                )
                if direct.status_code == 200 and direct.text.strip():
                    segments = _parse_vtt(direct.text)
                    if segments:
                        return segments

                listing = client.get(f"{base}/api/v1/captions/{video_id}")
                if listing.status_code != 200:
                    continue

                captions = listing.json().get("captions") or []
                if not captions:
                    continue

                preferred = None
                for cap in captions:
                    code = (cap.get("languageCode") or "").lower()
                    if code.startswith("en"):
                        preferred = cap
                        break
                preferred = preferred or captions[0]

                caption_url = preferred.get("url") or ""
                if caption_url.startswith("/"):
                    caption_url = base.rstrip("/") + caption_url

                caption_res = client.get(caption_url, params={"lang": "en"})
                if caption_res.status_code != 200 or not caption_res.text.strip():
                    continue

                segments = _parse_vtt(caption_res.text)
                if segments:
                    return segments
            except Exception:
                continue

    raise ValueError("Invidious caption fallback failed for all instances.")


def _get_transcript_youtube(api: YouTubeTranscriptApi, video_id: str) -> dict:
    raw_segments = None

    try:
        fetched = api.fetch(video_id, languages=["en"])
        raw_segments = list(fetched)
    except Exception:
        pass

    if raw_segments is None:
        try:
            transcript_list = api.list(video_id)
            transcript_obj = None

            try:
                transcript_obj = transcript_list.find_manually_created_transcript(["en"])
            except Exception:
                pass

            if transcript_obj is None:
                try:
                    transcript_obj = transcript_list.find_generated_transcript(["en"])
                except Exception:
                    pass

            if transcript_obj is None:
                available = list(transcript_list)
                if not available:
                    raise ValueError("No transcripts available for this video.")
                transcript_obj = available[0].translate("en")

            fetched = transcript_obj.fetch()
            raw_segments = list(fetched)

        except TranscriptsDisabled:
            raise ValueError("Transcripts are disabled for this video.")
        except NoTranscriptFound:
            raise ValueError(
                "No transcript found for this video. Make sure the video has captions enabled."
            )
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to fetch transcript: {str(e)}")

    segments = [_snippet_to_dict(s) for s in raw_segments]
    return _segments_to_result(video_id, segments)


def _text_to_result(video_id: str, full_text: str) -> dict:
    return {
        "video_id": video_id,
        "full_text": full_text,
        "segments": [{"text": full_text, "start": 0, "duration": 0}],
        "word_count": len(full_text.split()),
        "duration_seconds": 0,
    }


def _get_transcript_via_gemini(video_id: str) -> dict:
    from services.ai_service import transcribe_youtube_video

    full_text = transcribe_youtube_video(video_id)
    return _text_to_result(video_id, full_text)


def _is_cloud_host() -> bool:
    """Render/Railway/etc. IPs are blocked by YouTube — use Gemini there."""
    if os.getenv("TRANSCRIPT_MODE", "").strip().lower() == "gemini":
        return True
    return bool(
        os.getenv("RENDER")
        or os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("VERCEL")
        or os.getenv("FLY_APP_NAME")
    )


def _get_transcript_cloud(video_id: str) -> dict:
    if not os.getenv("GEMINI_API_KEY", "").strip():
        raise ValueError(
            "GEMINI_API_KEY is missing on Render. "
            "Dashboard → your service → Environment → add key from "
            "https://aistudio.google.com/app/apikey → Save → Redeploy."
        )
    return _get_transcript_via_gemini(video_id)


def get_transcript(video_id: str) -> dict:
    """
    Fetch transcript for a YouTube video.
    Local: YouTube API (fast). Cloud (Render): Gemini reads the YouTube URL.
    """
    if _is_cloud_host():
        return _get_transcript_cloud(video_id)

    api = _create_youtube_api()
    try:
        return _get_transcript_youtube(api, video_id)
    except ValueError as e:
        if not _is_ip_block_error(str(e)):
            raise
    except Exception as e:
        if not _is_ip_block_error(str(e)):
            raise ValueError(f"Failed to fetch transcript: {e}") from e

    if os.getenv("GEMINI_API_KEY", "").strip():
        return _get_transcript_via_gemini(video_id)

    raise ValueError(
        "YouTube blocked this IP and GEMINI_API_KEY is not set in .env."
    )
