"""Small shared utilities."""

import hashlib
import json
from pathlib import Path
from typing import Any

from slugify import slugify

DEFAULT_DECK_FILENAME = "deck.pdf"


def hash_string(s: str) -> str:
    """Return a stable SHA256 hex digest of a string (used as cache key)."""
    return hashlib.sha256(s.encode()).hexdigest()


def book_title_slug(cards: list[dict[str, Any]]) -> str | None:
    """
    Return a slug of the book title taken from the deck's `book_card`, or None.

    The book card is always the first card, but scan rather than index [0] so a
    deck the agent built in an unexpected order still resolves.
    """
    for card in cards:
        if card.get("type") == "book_card":
            title = str(card.get("title") or "").strip()
            if title:
                return slugify(title) or None
            break
    return None


def deck_filename(cards: list[dict[str, Any]]) -> str:
    """
    Return the deck PDF filename: `deck_{book-title-slug}.pdf`.

    Falls back to `deck.pdf` when the deck has no book card or no usable title —
    an old deck, or one the agent cut short.
    """
    slug = book_title_slug(cards)
    return f"deck_{slug}.pdf" if slug else DEFAULT_DECK_FILENAME


def deck_filename_from_json(cards_json: Path | bytes | None) -> str:
    """
    Same as `deck_filename`, reading the cards from a cards.json path or raw bytes.

    Never raises: unreadable or malformed JSON falls back to `deck.pdf`, since a
    filename is not worth failing a finished render over.
    """
    if cards_json is None:
        return DEFAULT_DECK_FILENAME
    try:
        raw = cards_json.read_bytes() if isinstance(cards_json, Path) else cards_json
        data = json.loads(raw)
        cards = data.get("cards") if isinstance(data, dict) else None
        return deck_filename(cards) if isinstance(cards, list) else DEFAULT_DECK_FILENAME
    except (OSError, ValueError, AttributeError):
        return DEFAULT_DECK_FILENAME
