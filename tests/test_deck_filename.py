"""Tests for the deck PDF filename derived from the book card title."""

import json
from pathlib import Path

from lib.utils import book_title_slug, deck_filename, deck_filename_from_json

BOOK_CARD = {
    "type": "book_card",
    "section": 0,
    "title": "The Lean Startup: How Today's Entrepreneurs Use Continuous Innovation",
    "author": "Eric Ries",
}
OTHER_CARD = {"type": "default", "section": 1, "title": "Build-Measure-Learn"}


def test_slug_comes_from_the_book_card() -> None:
    # NB: slugify turns the apostrophe into a separator ("today-s"), it does not drop it.
    slug = book_title_slug([BOOK_CARD, OTHER_CARD])
    assert slug == "the-lean-startup-how-today-s-entrepreneurs-use-continuous-innovation"


def test_filename_uses_the_book_title() -> None:
    assert deck_filename([BOOK_CARD]).startswith("deck_the-lean-startup")
    assert deck_filename([BOOK_CARD]).endswith(".pdf")


def test_book_card_found_even_when_not_first() -> None:
    """The book card is normally first, but the lookup must not depend on that."""
    assert deck_filename([OTHER_CARD, BOOK_CARD]) == deck_filename([BOOK_CARD])


def test_falls_back_when_no_book_card() -> None:
    assert deck_filename([OTHER_CARD]) == "deck.pdf"
    assert deck_filename([]) == "deck.pdf"


def test_falls_back_on_blank_title() -> None:
    assert deck_filename([{"type": "book_card", "title": "   "}]) == "deck.pdf"
    assert deck_filename([{"type": "book_card"}]) == "deck.pdf"


def test_reads_from_cards_json_path(tmp_path: Path) -> None:
    p = tmp_path / "cards.json"
    p.write_text(json.dumps({"cards": [BOOK_CARD, OTHER_CARD]}))
    assert deck_filename_from_json(p).startswith("deck_the-lean-startup")


def test_reads_from_raw_bytes() -> None:
    raw = json.dumps({"cards": [BOOK_CARD]}).encode()
    assert deck_filename_from_json(raw).startswith("deck_the-lean-startup")


def test_never_raises_on_bad_input(tmp_path: Path) -> None:
    """A filename is not worth failing a finished render over."""
    missing = tmp_path / "nope.json"
    assert deck_filename_from_json(missing) == "deck.pdf"
    assert deck_filename_from_json(b"not json at all") == "deck.pdf"
    assert deck_filename_from_json(json.dumps({"cards": "wrong type"}).encode()) == "deck.pdf"
    assert deck_filename_from_json(json.dumps([1, 2, 3]).encode()) == "deck.pdf"
    assert deck_filename_from_json(None) == "deck.pdf"
