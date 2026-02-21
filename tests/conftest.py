"""Shared pytest fixtures for Breaking Books v2 tests."""

from pathlib import Path

import pytest

from lib.models import Config, OutDir, WorkDir

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_book_html() -> str:
    """Return a small, deterministic HTML snippet for unit tests."""
    return (FIXTURES_DIR / "sample_book.html").read_text()


@pytest.fixture
def default_config() -> Config:
    return Config(num_cards=10, max_qc_calls=1)


@pytest.fixture
def tmp_work_dir(tmp_path: Path) -> WorkDir:
    return WorkDir.create(tmp_path / "tmp")


@pytest.fixture
def tmp_out_dir(tmp_path: Path) -> OutDir:
    return OutDir.create(tmp_path / "out")
