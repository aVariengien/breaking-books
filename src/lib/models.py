"""Core data models: Config, WorkDir, OutDir, VisualIdentity, BBGame."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from schemas import Card


class SectionTheme(BaseModel):
    """Theme for a card section."""

    accent_color: str = "#000000"


class VisualIdentity(BaseModel):
    """Visual identity for the game: fonts, colors, and aesthetic."""

    description: str = "Freeform description of the book's visual identity."
    title_font: str = "Arial"
    body_font: str = "Georgia"
    section_themes: list[SectionTheme] = []


class BBGame(BaseModel):
    """Top-level game structure: metadata + cards."""

    book_plan: str = "Freeform section plan and strategic notes."
    visual_identity: VisualIdentity = VisualIdentity()
    cards: list[Card] = []


class Config(BaseModel):
    num_cards: int = 40
    card_size: Literal["A5", "A6"] = "A6"
    language: str | None = None  # None → detect from book
    max_qc_calls: int = 3
    user_preferences: str = ""


class WorkDir(BaseModel):
    """Agent working directory layout (TMP/)."""

    root: Path

    @property
    def cards_json(self) -> Path:
        """TMP/cards.json — the live deck being edited by the agent."""
        return self.root / "cards.json"

    @property
    def renders_dir(self) -> Path:
        """TMP/renders/ — rendered PDFs and PNGs per card."""
        return self.root / "renders"

    @classmethod
    def create(cls, root: Path) -> "WorkDir":
        """Create directory structure on disk and return a WorkDir."""
        root.mkdir(parents=True, exist_ok=True)
        (root / "renders").mkdir(exist_ok=True)
        return cls(root=root)


class OutDir(BaseModel):
    """Output + snapshots directory layout (OUT/)."""

    root: Path

    @property
    def session_id_path(self) -> Path:
        """OUT/session_id.txt — Claude Agent SDK session ID for resume."""
        return self.root / "session_id.txt"

    @property
    def book_html_path(self) -> Path:
        """OUT/book.html — cached extracted book HTML, reused on resume."""
        return self.root / "book.html"

    @property
    def log_path(self) -> Path:
        """OUT/bb.log — full session log (appended across runs)."""
        return self.root / "bb.log"

    @property
    def images_dir(self) -> Path:
        """OUT/images/ — image cache keyed by SHA256(prompt), shared across runs."""
        return self.root / "images"

    def next_version(self) -> int:
        """Return the next unused version number (0-based)."""
        versions = []
        for p in self.root.glob("cards-v*.json"):
            try:
                versions.append(int(p.stem.split("-v")[1]))
            except (IndexError, ValueError):
                pass
        return max(versions) + 1 if versions else 0

    def cards_json_path(self, version: int) -> Path:
        """OUT/cards-v{version:03d}.json"""
        return self.root / f"cards-v{version:03d}.json"

    def qc_report_path(self, version: int) -> Path:
        """OUT/qc-report-v{version:03d}.md"""
        return self.root / f"qc-report-v{version:03d}.md"

    @classmethod
    def create(cls, root: Path) -> "OutDir":
        """Create directory structure on disk and return an OutDir."""
        root.mkdir(parents=True, exist_ok=True)
        (root / "images").mkdir(exist_ok=True)
        return cls(root=root)
