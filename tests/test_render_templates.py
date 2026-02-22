"""Test that all templates render without unexpected WeasyPrint warnings.

Uses the same cards, image cache, and render path as the Render Templates quality test.
Captures WeasyPrint logs during render and fails if any non-harmless warning appears.
"""

import logging
from pathlib import Path

from tools.render_template import PREDEFINED_STYLES, render_all_templates

ROOT = Path(__file__).parents[1]
IMAGE_CACHE_DIR = ROOT / "data" / "image_cache"


def test_all_templates_render_without_unexpected_weasyprint_warnings(tmp_path: Path) -> None:
    """Render every template with example cards; fail if WeasyPrint emits new warnings."""
    wp_logger = logging.getLogger("weasyprint")
    old_propagate = wp_logger.propagate
    wp_logger.propagate = False  # Don't flood pytest's captured logs with benign CDN CSS warnings
    try:
        results = render_all_templates(
            tmp_path,
            IMAGE_CACHE_DIR,
            PREDEFINED_STYLES["classic"].model_dump(),
        )
        failures = [(r.card_type, r.template_name, r.warnings) for r in results if r.warnings]
        if failures:
            lines = [
                f"  {card_type} / {template_name}: {w}"
                for card_type, template_name, warns in failures
                for w in warns
            ]
            raise AssertionError(
                "WeasyPrint emitted unexpected warnings. "
                "This is likely due to using a feature that WeasyPrint does not support and needs to be fixed. "
                "If certain the warnings are harmless, add to HARMLESS_CSS_PATTERNS in tools/render_template.py."
                "\n" + "\n".join(lines)
            )
    finally:
        wp_logger.propagate = old_propagate
