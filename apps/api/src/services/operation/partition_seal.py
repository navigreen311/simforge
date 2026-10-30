"""The digest a partition is sealed with (ADR-0109, ADR-0162).

Its own module so the grader can recompute a seal without importing the authoring service,
which no router may reach (`test_no_router_can_reach_the_partition`). It reads nothing: it is
given digests and returns one.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable


def content_digest(digests: Iterable[str], roster: str | None = None) -> str:
    """sha256 over the sorted scenario digests, newline-joined.

    ADR-0162. With a recorded roster, its digest follows as one more line, `roster:<hex>`, so
    the seal binds who sits as well as what is put. A scenario digest is bare hex and never
    holds a colon, so that line cannot be one. Without a roster the digest is exactly as
    before: an older partition's seal still reads true.
    """
    lines = sorted(digests)
    if roster is not None:
        lines.append(f"roster:{roster}")
    joined = "\n".join(lines)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


__all__ = ["content_digest"]
