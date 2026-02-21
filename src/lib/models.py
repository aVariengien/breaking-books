"""Core data models: Config, WorkDir, OutDir."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel


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
        raise NotImplementedError()

    @property
    def images_dir(self) -> Path:
        """TMP/images/ — image cache keyed by prompt hash."""
        raise NotImplementedError()

    @property
    def renders_dir(self) -> Path:
        """TMP/renders/ — rendered PDFs and PNGs per card."""
        raise NotImplementedError()

    @classmethod
    def create(cls, root: Path) -> "WorkDir":
        """Create directory structure on disk and return a WorkDir."""
        raise NotImplementedError()


class OutDir(BaseModel):
    """Output + snapshots directory layout (OUT/)."""

    root: Path

    def next_version(self) -> int:
        """Return the next unused version number (0-based)."""
        raise NotImplementedError()

    def cards_json_path(self, version: int) -> Path:
        """OUT/cards-v{version:03d}.json"""
        raise NotImplementedError()

    def qc_report_path(self, version: int) -> Path:
        """OUT/qc-report-v{version:03d}.md"""
        raise NotImplementedError()

    @classmethod
    def create(cls, root: Path) -> "OutDir":
        """Create directory structure on disk and return an OutDir."""
        raise NotImplementedError()
