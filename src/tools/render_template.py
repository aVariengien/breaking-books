"""Render card dicts to PDF via Jinja2 + WeasyPrint."""

import json
import random
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from joblib import Parallel, delayed

from lib.models import Config
from lib.registry import get_all_schema_classes
from schemas._base import Schema
from tools.generate_images import get_image_base64

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def render_card_to_pdf(
    card: dict,
    template_name: str,
    output_dir: Path,
    images_dir: Path,
    *,
    card_index: int,
    visual_identity: dict | None = None,
) -> Path:
    """
    Render a single card dict with the named Jinja2 template to a PDF file.

    - Loads the template from src/templates/.
    - Exposes get_image(prompt, width, height) callable to the template.
    - Passes visual_identity (fonts, colors) to template for styling.
    - Writes output to `output_dir/card-{card_index}.pdf`.
    - Returns the path to the generated PDF.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(template_name)

    template_vars = dict(card)

    # Expose image generation function to template
    def get_image(prompt: str, width: int = 768, height: int = 512) -> str | None:
        """Generate or retrieve a cached image as base64. Called from Jinja2 templates."""
        return get_image_base64(prompt, images_dir, size=(height, width))

    # Visual identity vars are the base layer; card fields override them if names collide.
    # (e.g. visual_identity.description must not clobber card.description)
    merged: dict = {}
    if visual_identity:
        merged.update(visual_identity)
    merged.update(template_vars)
    merged["get_image"] = get_image
    template_vars = merged

    rendered_html = template.render(**template_vars)

    pdf_path = output_dir / f"card-{card_index}.pdf"
    from weasyprint import HTML  # lazy import — requires libgobject/pango at runtime only
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
    Render all cards in bbGame.cards to individual PDF files.

    Selects a template for each card (randomly from schema.templates, or as
    specified in the card dict). Runs in parallel via joblib when n_jobs != 1.

    Returns the list of generated PDF paths, in card order.
    """
    from lib.models import BBGame

    output_dir.mkdir(parents=True, exist_ok=True)
    game_data = json.loads(cards_json_path.read_text(encoding="utf-8"))
    game = BBGame.model_validate(game_data)
    cards = [c.model_dump() for c in game.cards]

    # Build map: card type string → schema class
    schema_by_type: dict[str, type[Schema]] = {}
    for cls in get_all_schema_classes():
        type_field = cls.model_fields.get("type")
        if type_field and type_field.default:
            schema_by_type[type_field.default] = cls

    from lib.models import SectionTheme

    # Config values injected into every card's template context
    config_vars = {
        "card_size": config.card_size,
        "language": config.language or "en",
    }

    def _vi_vars(card: dict) -> dict:
        """Return flat visual-identity vars for this card, resolved to its section theme."""
        vi = game.visual_identity
        section = card.get("section", 0) or 0
        themes = vi.section_themes
        theme = themes[section] if 0 <= section < len(themes) else SectionTheme()
        return {
            "title_font": vi.title_font,
            "body_font": vi.body_font,
            "main_color": theme.main_color,
            "accent_color": theme.accent_color,
            "dark_color": theme.dark_color,
        }

    def _resolve_template(card: dict) -> str:
        if "template" in card:
            return card["template"]
        card_type = card.get("type", "")
        schema_cls = schema_by_type.get(card_type)
        if schema_cls and schema_cls.templates:
            return random.choice(schema_cls.templates)
        raise ValueError(f"No template found for card type {card_type!r}")

    tasks = [
        (i, {**config_vars, **card}, _resolve_template(card), _vi_vars(card))
        for i, card in enumerate(cards)
    ]

    results: list[Path] = Parallel(n_jobs=n_jobs)(
        delayed(render_card_to_pdf)(
            card_data,
            template_name,
            output_dir,
            images_dir,
            card_index=i,
            visual_identity=vi_vars,
        )
        for i, card_data, template_name, vi_vars in tasks
    )
    return results
