"""Prompt template loading for LLM-judge scorers (ADR-0008)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template

_DIR = Path(__file__).parent


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Load a `.txt` prompt template by name (without extension)."""
    path = _DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **vars: object) -> str:
    """Load + `string.Template` safe-substitute a prompt."""
    return Template(load_prompt(name)).safe_substitute(**vars)
