"""Video / YouTube transcript ingestion (Batch 6, ADR-0043).

Two capabilities, each an independently-gated seam that turns spoken media into text — which then
feeds the SAME `extract_scenario` → human-review → commit path as every other source. The cardinal
rule is unchanged: a transcript becomes an AI-drafted DRAFT a human approves and separately commits,
and nothing is fabricated (a video with no captions, or an unconfigured provider, is an honest
error, never an invented transcript).

  * YouTube captions (gate G3): fetch an existing caption track for a YouTube URL via
    youtube-transcript-api. No API key, but it makes a network call, so it is OFF by default
    (`TRANSCRIPT_YOUTUBE_ENABLED`) to keep CI hermetic. Only works when the video HAS captions —
    it does not transcribe audio.
  * Audio-file transcription (gate G2): transcribe an uploaded audio file via a provider
    (OpenAI Whisper, raw HTTPS — no vendor SDK). Key-gated; stub → honest "not configured".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.config import settings

# Cap transcript text to fit the extraction single-pass budget (12k) with headroom.
_MAX_TRANSCRIPT_CHARS = 10_000
# OpenAI's transcription endpoint caps uploads at 25 MB.
_MAX_AUDIO_BYTES = 25 * 1024 * 1024
_AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".webm", ".mp4", ".mpeg", ".mpga", ".oga", ".ogg", ".flac"}

_YT_ID = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/|v/))([A-Za-z0-9_-]{11})"
)


class TranscriptUnavailable(Exception):
    """A transcript capability was requested but is not configured (no fabrication, no fallback)."""


@dataclass
class TranscriptResult:
    ok: bool
    text: str = ""
    error: str | None = None
    source_kind: str = ""  # youtube | file
    meta: dict = field(default_factory=dict)


def youtube_video_id(url: str) -> str | None:
    """Extract an 11-char YouTube video id from common URL forms (or None)."""
    m = _YT_ID.search(url or "")
    if m:
        return m.group(1)
    bare = (url or "").strip()
    return bare if re.fullmatch(r"[A-Za-z0-9_-]{11}", bare) else None


def youtube_available() -> bool:
    """True only when YouTube caption fetching is enabled AND the library is importable."""
    if not settings.transcript_youtube_enabled:
        return False
    try:
        import youtube_transcript_api  # noqa: F401

        return True
    except ImportError:
        return False


def file_transcription_available() -> bool:
    """True only when an audio-transcription provider is fully configured."""
    return settings.transcript_provider == "openai" and bool(settings.openai_api_key)


def fetch_youtube_transcript(url: str) -> TranscriptResult:
    """Fetch an existing YouTube caption track. Never transcribes audio; never fabricates."""
    if not youtube_available():
        raise TranscriptUnavailable(
            "YouTube transcript ingestion is not enabled. Set TRANSCRIPT_YOUTUBE_ENABLED=true "
            "(needs the youtube-transcript-api library). No transcript is fabricated."
        )
    video_id = youtube_video_id(url)
    if not video_id:
        return TranscriptResult(
            ok=False, source_kind="youtube", error="Not a recognizable YouTube URL or video id."
        )
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        fetched = YouTubeTranscriptApi().fetch(video_id, languages=("en",))
        snippets = list(fetched)
        text = " ".join(s.text.strip() for s in snippets if s.text.strip())
    except Exception as exc:  # noqa: BLE001 — captions disabled / none / blocked → honest error
        return TranscriptResult(
            ok=False,
            source_kind="youtube",
            error=f"Could not fetch a transcript for this video: {type(exc).__name__}: {exc}",
        )
    if len(text) < 40:
        return TranscriptResult(
            ok=False,
            source_kind="youtube",
            error="The video has no usable caption text (it may have captions disabled).",
        )
    return TranscriptResult(
        ok=True,
        source_kind="youtube",
        text=text[:_MAX_TRANSCRIPT_CHARS],
        meta={"video_id": video_id, "segments": len(snippets)},
    )


async def transcribe_audio_file(filename: str, data: bytes) -> TranscriptResult:
    """Transcribe an uploaded audio file via the configured provider. Never fabricates."""
    if not file_transcription_available():
        raise TranscriptUnavailable(
            "Audio transcription is not configured. Set TRANSCRIPT_PROVIDER=openai and "
            "OPENAI_API_KEY to enable it. No transcript is fabricated."
        )
    ext = filename[filename.rfind(".") :].lower() if "." in filename else ""
    if ext not in _AUDIO_EXTS:
        return TranscriptResult(
            ok=False,
            source_kind="file",
            error=f"Unsupported audio type '{ext or '(none)'}'. Supported: "
            f"{', '.join(sorted(e.lstrip('.') for e in _AUDIO_EXTS))}.",
        )
    if not data:
        return TranscriptResult(ok=False, source_kind="file", error="The uploaded file is empty.")
    if len(data) > _MAX_AUDIO_BYTES:
        return TranscriptResult(
            ok=False,
            source_kind="file",
            error=f"File is {len(data) // 1024 // 1024} MB — over the 25 MB transcription limit.",
        )
    try:
        text = await _openai_transcribe(filename, data)
    except Exception as exc:  # noqa: BLE001 — provider/network error surfaced honestly
        return TranscriptResult(
            ok=False, source_kind="file", error=f"Transcription failed: {type(exc).__name__}: {exc}"
        )
    if len(text.strip()) < 40:
        return TranscriptResult(
            ok=False, source_kind="file", error="Almost no speech was transcribed from the audio."
        )
    return TranscriptResult(ok=True, source_kind="file", text=text.strip()[:_MAX_TRANSCRIPT_CHARS])


async def _openai_transcribe(filename: str, data: bytes) -> str:
    """Raw HTTPS call to OpenAI's audio-transcription endpoint (no vendor SDK, like Tavily)."""
    import httpx

    async with httpx.AsyncClient(timeout=settings.transcript_timeout_seconds) as client:
        resp = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            files={"file": (filename, data)},
            data={"model": settings.openai_transcribe_model, "response_format": "text"},
        )
        resp.raise_for_status()
        return resp.text
