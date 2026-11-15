"""Ollama's own record of every request it served, read to tell whether an exam was alone.

Ivan Green, 14 November 2026 (ADR-0167): every exam and partition grading records whether any
other phi4 request happened between its first and last model call. If one did, the grading is
NOT RUN: nothing posted, the run stays open, it re-sits at the next opportunity, logged as
"another phi4 caller during the exam". Measured that morning: one concurrent caller changed 33 of
57 answers while every exam call still loaded the model cold, so the clean-cache rule (B135) did
not see it.

WHY THE REQUEST LOG, AND NOT /api/ps OR A COUNTER
=================================================

- **The server's request log** (`server.log`) writes one `[GIN]` line per request Ollama served,
  whoever sent it, as the request completes. It is the only one of the three that records the
  other callers' requests themselves rather than a side effect of them.
- `/api/ps` shows what is loaded and until when (`expires_at`). The exam unloads before every
  call, so a co-caller's request between two exam calls leaves no trace there, and one during an
  exam call only moves `expires_at` by a second or two, which a poll can miss.
- Ollama keeps no request counter (no `/metrics`), so there is none to read.

HOW IT DECIDES
==============

The exam knows exactly which requests it sent: every unload (`POST /api/generate` with
`keep_alive: 0`) and every call (`POST /api/chat`). A watch notes the log's size before the exam's
first request, then counts the model requests the log gained (`/api/chat`, `/api/generate`,
`/api/embed`, `/api/embeddings`; never `/api/ps`, `/api/tags` or `/api/show`, which run no model).
More than the exam sent means another caller. The lines carry no model name, so a request for any
model counts: on one machine's one GPU, any other generation is a co-tenant of the exam.

A line is written when a request ends, so a request still running at a check shows up at a later
one. At the end of a grading the exam unloads the model and waits for `/api/ps` to empty, which
Ollama does only once no request holds it, and then reads the log a last time.

If the log cannot be read, or is not the file the exam began on (Ollama restarted and began a new
one: it shrank, or its identity or first bytes changed), whether the exam was alone cannot be told,
and it is not graded either: the same NOT RUN.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

#: The reason every voided grading carries (Ivan Green, 14 November 2026).
ANOTHER_CALLER = "another phi4 caller during the exam"

#: Requests that run a model. Everything else Ollama serves (`/api/ps`, `/api/tags`, `/api/show`,
#: `/api/version`) only reads.
MODEL_PATHS = frozenset({"/api/chat", "/api/generate", "/api/embed", "/api/embeddings"})

#: `[GIN] 2026/11/14 - 09:55:23 | 200 |    2.0068068s |       127.0.0.1 | POST     "/api/chat"`
_GIN = re.compile(
    r'^\[GIN\][^|]*\|\s*\d{3}\s*\|[^|]*\|[^|]*\|\s*(?P<method>[A-Z]+)\s+"(?P<path>[^"?]+)'
)


def default_path() -> Path | None:
    """Where Ollama for Windows writes its server log: `%LOCALAPPDATA%\\Ollama\\server.log`."""
    local = os.environ.get("LOCALAPPDATA")
    return Path(local) / "Ollama" / "server.log" if local else None


class RequestLogUnreadable(OSError):
    """The log cannot tell whether the exam was alone."""


@dataclass
class Watch:
    """The log from one exam's first request on."""

    path: Path
    offset: int
    #: The file's first bytes at the start: a new log (Ollama restarted) begins differently.
    head: bytes = b""
    #: The file's identity at the start, where the platform gives one.
    ident: tuple[int, int] | None = None

    def model_requests(self) -> int:
        """Model requests the log gained since the watch began. Whole lines only: a line still
        being written is counted at the next read."""
        try:
            st = self.path.stat()
            size = st.st_size
            moved = self.ident is not None and st.st_ino and (st.st_dev, st.st_ino) != self.ident
            if size < self.offset or moved:
                raise RequestLogUnreadable(
                    f"{self.path} is not the log the exam began on (Ollama began a new one)"
                )
            with self.path.open("rb") as f:
                if self.head and f.read(len(self.head)) != self.head:
                    raise RequestLogUnreadable(
                        f"{self.path} is not the log the exam began on (Ollama began a new one)"
                    )
                f.seek(self.offset)
                tail = f.read(size - self.offset)
        except RequestLogUnreadable:
            raise
        except OSError as exc:
            raise RequestLogUnreadable(f"{self.path} cannot be read: {type(exc).__name__}") from exc
        complete = tail[: tail.rfind(b"\n") + 1].decode("utf-8", "replace")
        return sum(
            1
            for line in complete.splitlines()
            if (m := _GIN.match(line)) and m["method"] == "POST" and m["path"] in MODEL_PATHS
        )


@dataclass(frozen=True)
class RequestLog:
    """Ollama's server log, or where it should be."""

    path: Path | None

    @classmethod
    def from_settings(cls) -> RequestLog:
        from src.config import settings

        named = getattr(settings, "ollama_request_log", "") or ""
        return cls(Path(named) if named else default_path())

    def begin(self) -> Watch:
        """A watch from here on. Raises `RequestLogUnreadable` with no log to read."""
        if self.path is None:
            raise RequestLogUnreadable("no Ollama request log is configured (OLLAMA_REQUEST_LOG)")
        try:
            st = self.path.stat()
            with self.path.open("rb") as f:
                head = f.read(min(st.st_size, 256))
            ident = (st.st_dev, st.st_ino) if st.st_ino else None
            return Watch(self.path, st.st_size, head, ident)
        except OSError as exc:
            raise RequestLogUnreadable(f"{self.path} cannot be read: {type(exc).__name__}") from exc
