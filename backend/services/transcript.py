import re
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)


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


def _snippet_to_dict(snippet) -> dict:
    """Normalise a FetchedTranscriptSnippet (v1.x) or plain dict (v0.x) to dict."""
    if isinstance(snippet, dict):
        return snippet
    return {
        "text": snippet.text,
        "start": snippet.start,
        "duration": snippet.duration,
    }


def get_transcript(video_id: str) -> dict:
    """
    Fetch the transcript for a YouTube video.
    Compatible with youtube-transcript-api >= 1.0.

    Returns a dict with:
      full_text        – full concatenated transcript string
      segments         – list of {text, start, duration} dicts
      word_count       – approximate word count
      duration_seconds – total video duration from transcript
    """
    api = YouTubeTranscriptApi()

    raw_segments = None

    # ── 1. Try direct English fetch ─────────────────────────────────────────
    try:
        fetched = api.fetch(video_id, languages=["en"])
        raw_segments = list(fetched)
    except Exception:
        pass

    # ── 2. Fall back: list transcripts and pick the best one ────────────────
    if raw_segments is None:
        try:
            transcript_list = api.list(video_id)

            transcript_obj = None

            # Prefer manually created English
            try:
                transcript_obj = transcript_list.find_manually_created_transcript(["en"])
            except Exception:
                pass

            # Then auto-generated English
            if transcript_obj is None:
                try:
                    transcript_obj = transcript_list.find_generated_transcript(["en"])
                except Exception:
                    pass

            # Then any language, translate to English
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

    # ── 3. Normalise snippets to plain dicts ─────────────────────────────────
    segments = [_snippet_to_dict(s) for s in raw_segments]

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
