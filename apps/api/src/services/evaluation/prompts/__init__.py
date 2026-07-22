"""Locale-aware prompt template loading for LLM-judge scorers (ADR-0008 / ADR-0041).

A template `name` resolves to `{name}.{locale}.txt` when that locale file exists, else the English
base `{name}.txt`. English uses the base file (no `en` suffix), so the default path is unchanged and
existing scores are stable; a pack that declares another locale gets the translated rubric prompts.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template

_DIR = Path(__file__).parent
_DEFAULT_LOCALE = "en"


def available_locales(name: str) -> list[str]:
    """Locales a given prompt is translated into (always includes the base `en`)."""
    locales = {_DEFAULT_LOCALE} if (_DIR / f"{name}.txt").exists() else set()
    for path in _DIR.glob(f"{name}.*.txt"):
        # `p7_cx.es.txt` → the middle segment is the locale.
        locales.add(path.name[len(name) + 1 : -len(".txt")])
    return sorted(locales)


@lru_cache(maxsize=128)
def load_prompt(name: str, locale: str = _DEFAULT_LOCALE) -> str:
    """Load a prompt template, preferring the locale variant and falling back to the base."""
    if locale and locale != _DEFAULT_LOCALE:
        localized = _DIR / f"{name}.{locale}.txt"
        if localized.exists():
            return localized.read_text(encoding="utf-8")
    base = _DIR / f"{name}.txt"
    if not base.exists():
        raise FileNotFoundError(f"Prompt template not found: {base}")
    return base.read_text(encoding="utf-8")


def render_prompt(name: str, *, locale: str = _DEFAULT_LOCALE, **vars: object) -> str:
    """Load + `string.Template` safe-substitute a prompt in the requested locale."""
    return Template(load_prompt(name, locale)).safe_substitute(**vars)
