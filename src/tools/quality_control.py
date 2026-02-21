"""
Quality Control tool.

Called by the agent after writing or updating cards.json. Runs a multi-step
inspection and returns a natural-language improvement report. Also saves a
versioned snapshot of cards.json + report to OutDir.
"""

from pathlib import Path

from lib.models import Config, OutDir, WorkDir


def quality_control(
    cards_json_path: Path,
    config: Config,
    work_dir: WorkDir,
    out_dir: OutDir,
) -> str:
    """
    Run full quality control on cards.json.

    Steps (in order):
    1. _check_json_structure  — parse & validate against schemas
    2. _check_section_balance — warn if sections have unequal card counts
    3. _llm_review            — language, style, completeness, interest
    4. _visual_review         — render to PDF/PNG, vision LLM per card

    Saves a versioned snapshot: OUT/cards-vNNN.json + OUT/qc-report-vNNN.md.

    Returns a natural-language string listing possible improvements,
    which the agent can incorporate (or not) in subsequent edits.
    """
    raise NotImplementedError()


# ------------------------------------------------------------------
# Internal steps
# ------------------------------------------------------------------


def _check_json_structure(cards_json_path: Path) -> list[str]:
    """Parse cards.json; return a list of structural / schema validation errors."""
    raise NotImplementedError()


def _check_section_balance(cards: list[dict]) -> list[str]:
    """Return warning strings if sections have significantly unequal card counts."""
    raise NotImplementedError()


def _llm_review(cards: list[dict], config: Config) -> str:
    """
    Ask an LLM to review all cards and return a quality assessment covering:
    - All terms defined?
    - Language consistent and correct?
    - Style coherent across cards?
    - Exhaustive coverage of the book's key ideas?
    - Interesting and well-scoped?
    - Type adherence (right card type for each card)?
    """
    raise NotImplementedError()


def _visual_review(cards_json_path: Path, config: Config, work_dir: WorkDir) -> str:
    """
    Render each card to PNG (via render_template + pdf_to_pngs), then run one
    vision LLM call per card checking for: text cut off, layout overflow,
    missing image, color contrast issues, and other visual defects.

    Returns a summary string of visual issues found.
    """
    raise NotImplementedError()
