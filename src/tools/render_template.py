"""Render card dicts to PDF via Jinja2 + WeasyPrint."""

import base64
import json
import random
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from joblib import Parallel, delayed
from weasyprint import HTML

from lib.models import Config
from lib.registry import get_all_schema_classes
from schemas._base import Schema
from tools.generate_images import image_cache_path

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def render_card_to_pdf(card: dict, template_name: str, output_dir: Path, images_dir: Path) -> Path:
    """
    Render a single card dict with the named Jinja2 template to a PDF file.

    - Loads the template from src/templates/.
    - Resolves image_base64 from the image cache via image_cache_path(image_description, images_dir).
    - Writes output to `output_dir/{card_id}.pdf`.
    - Returns the path to the generated PDF.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(template_name)

    template_vars = dict(card)

    # Resolve image from cache using the description as the key
    image_description = template_vars.get("image_description")
    if image_description:
        img_path = image_cache_path(image_description, images_dir)
        template_vars["image_base64"] = (
            base64.b64encode(img_path.read_bytes()).decode() if img_path.exists() else None
        )
    else:
        template_vars["image_base64"] = None

    rendered_html = template.render(**template_vars)

    card_id = card.get("id", "card")
    pdf_path = output_dir / f"{card_id}.pdf"
    HTML(string=rendered_html, base_url=str(_TEMPLATES_DIR)).write_pdf(pdf_path)
    return pdf_path


def cards_json_to_pdfs(
    cards_json_path: Path,
    output_dir: Path,
    config: Config,
    images_dir: Path,
    *,
    n_jobs: int = -1,
) -> list[Path]:
    """
    Render all cards in cards.json to individual PDF files.

    Selects a template for each card (randomly from schema.templates, or as
    specified in the card dict). Runs in parallel via joblib when n_jobs != 1.

    Returns the list of generated PDF paths, in card order.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    cards: list[dict] = json.loads(cards_json_path.read_text(encoding="utf-8"))

    # Build map: card type string → schema class
    schema_by_type: dict[str, type[Schema]] = {}
    for cls in get_all_schema_classes():
        type_field = cls.model_fields.get("type")
        if type_field and type_field.default:
            schema_by_type[type_field.default] = cls

    # Config values injected into every card's template context
    config_vars = {
        "card_size": config.card_size,
        "language": config.language or "en",
    }

    def _resolve_template(card: dict) -> str:
        if "template" in card:
            return card["template"]
        card_type = card.get("type", "")
        schema_cls = schema_by_type.get(card_type)
        if schema_cls and schema_cls.templates:
            return random.choice(schema_cls.templates)
        raise ValueError(f"No template found for card type {card_type!r}")

    tasks = [({**config_vars, **card}, _resolve_template(card)) for card in cards]

    results: list[Path] = Parallel(n_jobs=n_jobs)(
        delayed(render_card_to_pdf)(card_data, template_name, output_dir, images_dir)
        for card_data, template_name in tasks
    )
    return results
