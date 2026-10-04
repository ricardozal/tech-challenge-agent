"""Text normalization shared by rules and providers (pure)."""

import re
import unicodedata

_NON_WORD = re.compile(r"[^A-Z0-9 ]+")
_SPACES = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def normalize(text: str | int | None) -> str:
    """Uppercase, no accents, no punctuation, single spaces."""
    if text is None:
        return ""
    upper = strip_accents(str(text)).upper()
    return _SPACES.sub(" ", _NON_WORD.sub(" ", upper)).strip()
