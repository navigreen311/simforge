"""Document → text extraction (Batch 3).

Pulls plain text out of an uploaded PDF / DOCX / TXT / MD so it can feed the same
extraction path as pasted text. This step does NOT call an LLM and does NOT create a scenario — it
only turns a file into text (or an honest error). No OCR: a scanned/image-only PDF yields little or
no text, and we say so rather than inventing content.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

# Guardrail: reject anything above this so a huge upload can't wedge the request. The extraction
# step has its own (smaller) single-pass char budget; this is just the raw-bytes gate.
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB
_MIN_USEFUL_CHARS = 40

_TEXT_EXTS = {".txt", ".md", ".markdown", ".rst"}
_SUPPORTED = _TEXT_EXTS | {".pdf", ".docx"}


@dataclass
class DocumentText:
    ok: bool
    text: str = ""
    error: str | None = None
    kind: str = ""  # pdf | docx | text


def _ext(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def _docx_text(data: bytes) -> str:
    import docx

    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs).strip()


def extract_document_text(filename: str, data: bytes) -> DocumentText:
    """Extract text from an uploaded file. Never fabricates — empty/unreadable → a clear error."""
    ext = _ext(filename)
    if ext not in _SUPPORTED:
        return DocumentText(
            ok=False,
            error=f"Unsupported file type '{ext or '(none)'}'. Supported: PDF, DOCX, TXT, MD.",
        )
    if not data:
        return DocumentText(ok=False, error="The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        mb = MAX_UPLOAD_BYTES // 1024 // 1024
        return DocumentText(
            ok=False,
            error=f"File is {len(data) // 1024} KB — over the {mb} MB limit. "
            "Split it or paste the relevant passage instead.",
        )

    try:
        if ext in _TEXT_EXTS:
            text, kind = data.decode("utf-8", errors="replace").strip(), "text"
        elif ext == ".pdf":
            text, kind = _pdf_text(data), "pdf"
        else:  # .docx
            text, kind = _docx_text(data), "docx"
    except Exception as exc:  # noqa: BLE001 — surface any parse failure as an honest error
        return DocumentText(ok=False, error=f"Could not read the {ext} file: {exc}")

    if len(text) < _MIN_USEFUL_CHARS:
        return DocumentText(
            ok=False,
            kind=kind,
            error="Almost no text could be extracted. If this is a scanned/image PDF, it needs OCR "
            "(not supported) — paste the text instead.",
        )
    return DocumentText(ok=True, text=text, kind=kind)
