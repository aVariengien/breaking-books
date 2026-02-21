"""Render card dicts to PDF via Jinja2 + WeasyPrint."""

from pathlib import Path

from lib.models import Config


def render_card_to_pdf(card: dict, template_name: str, output_dir: Path) -> Path:
    """
    Render a single card dict with the named Jinja2 template to a PDF file.

    - Loads the template from src/templates/.
    - Writes output to `output_dir/{card_id}.pdf`.
    - Returns the path to the generated PDF.
    """
    raise NotImplementedError()


def cards_json_to_pdfs(
    cards_json_path: Path,
    output_dir: Path,
    config: Config,
    *,
    n_jobs: int = -1,
) -> list[Path]:
    """
    Render all cards in cards.json to individual PDF files.

    Selects a template for each card (randomly from schema.templates, or as
    specified in the card dict). Runs in parallel via joblib when n_jobs != 1.

    Returns the list of generated PDF paths, in card order.
    """
    raise NotImplementedError()
