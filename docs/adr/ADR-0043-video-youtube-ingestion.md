# ADR-0043 — Video / YouTube transcript ingestion for the Scenario Bank

**Status:** Accepted (2026-07-26).

## Context
Batch 6 of the Scenario Bank spec is the last ingestion method: turn a talk, interview, or training
video into a scenario. It was previously an honest "pending dependency" stub (Batch 4 gate G2
transcription / G3 youtube-fetch). The same two constraints apply as every other source: nothing
auto-commits (a transcript becomes an AI-drafted DRAFT a human reviews and separately commits), and
nothing is fabricated (a video with no captions, or an unconfigured provider, is an honest error —
never an invented transcript).

Speech-to-text splits into two genuinely different capabilities, so the gate had two sub-parts:
- **G3 — fetch an existing caption track** for a YouTube video (no transcription needed).
- **G2 — transcribe audio** for media that has no captions (an uploaded recording).

## Decision
- **Two independently-gated seams in `services/scenario_bank/transcript.py`**, both OFF by default so
  the Video tab honestly reports "not configured" and CI never hits the network.
  - **YouTube captions** via `youtube-transcript-api` (pure-Python, **no API key**). Fetches the
    English caption track for a URL/id; only works when the video *has* captions — it does not
    transcribe audio. Gated on `TRANSCRIPT_YOUTUBE_ENABLED` because it makes a network call.
  - **Audio-file transcription** via OpenAI Whisper, called over **raw HTTPS with httpx (no vendor
    SDK)** — the same approach as `TavilyProvider`, so no `openai` dependency is added. Gated on
    `TRANSCRIPT_PROVIDER=openai` + `OPENAI_API_KEY`; a stub raises `TranscriptUnavailable`.
- **Maximal reuse.** Transcript endpoints only *produce text*. The transcript feeds the **existing**
  `POST /extract` (`source_type="youtube"|"video"`, `source_ref=url/filename`), so extraction, the
  human review form, two-stage promotion, and the `derived_from` Lineage edge all work with no new
  code. Transcript text is truncated to 10k chars to fit the extraction budget; audio uploads are
  capped at 25 MB (OpenAI's limit).
- **Honest availability surface.** `GET /transcript/status` returns `{youtube_available,
  file_available}` so the UI shows only the capabilities that are configured, and the "not
  configured" empty state when neither is. `POST /transcript/youtube` and `/transcript/file` return
  `available=false` + a plain message rather than a fake transcript.

## Consequences
- YouTube ingestion is activatable with **no paid key** — set `TRANSCRIPT_YOUTUBE_ENABLED=true`. This
  makes the whole chain (URL → transcript → extraction → draft) demoable end-to-end in dev. Its
  limitation is inherent: no captions → honest failure (it does not fall back to audio transcription).
- Audio-file transcription activates with an OpenAI key; video files needing audio extraction
  (ffmpeg) and local Whisper are deliberately out of scope — the seam accepts audio formats Whisper
  takes directly.
- `youtube-transcript-api` scrapes YouTube's internal endpoints, so it can be rate-limited or blocked
  from datacenter IPs; any such failure surfaces as an honest error, never a fabricated transcript.
- This completes the Scenario Bank ingestion methods: manual, paste, document, web search, and
  video/YouTube — all funnelling into one review-then-commit path.
