"""Quality test: render_template — card schema + Jinja2 template → PDF → PNG.

Renders one card per schema type × template using hardcoded example data.
If quality_tests/fixtures/sample_image.png exists, it is used as the card
image; otherwise cards render with a text placeholder.

CLI:      python quality_tests/pages/2_Render_Templates.py
Streamlit: make quality-tests → "Render Templates" page
"""

import base64
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from lib.registry import get_all_schema_classes  # noqa: E402
from lib.streamlit_utils import in_streamlit  # noqa: E402
from tools.pdf_to_pngs import pdf_to_pngs  # noqa: E402
from tools.render_template import render_card_to_pdf  # noqa: E402

FIXTURES_DIR = ROOT / "quality_tests" / "fixtures"
SAMPLE_IMAGE = FIXTURES_DIR / "sample_image.png"

# ---------------------------------------------------------------------------
# Hardcoded example cards — add one entry per schema type.
# ---------------------------------------------------------------------------
EXAMPLE_CARDS: dict[str, dict] = {
    "concept": {
        "type": "concept",
        "section": 0,
        "title": "The Ratchet Effect",
        "book_quotes": [
            "Once a cultural or technological innovation is adopted, it tends to persist "
            "and accumulate rather than slip back.",
            "Humans, unlike other animals, routinely build on the achievements of "
            "prior generations without having to reinvent them.",
        ],
        "image_description": (
            "A stone staircase carved into a cliff face, winding upward into the mist, "
            "each step worn smooth by centuries of use. Soft natural light from above."
        ),
    },
}


def _render_to_png_bytes(
    card: dict,
    template_name: str,
    card_size: str,
    dpi: int = 150,
) -> bytes:
    """Render a card dict to PNG bytes (single-page card assumed)."""
    card_data = {**card, "card_size": card_size, "language": "en"}
    if SAMPLE_IMAGE.exists():
        card_data["image_base64"] = base64.b64encode(SAMPLE_IMAGE.read_bytes()).decode()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        images_dir = tmp_dir / "images"
        pdf = render_card_to_pdf(card_data, template_name, tmp_dir, images_dir, card_index=0)
        pngs = pdf_to_pngs(pdf, tmp_dir / "pngs", dpi=dpi)
        return pngs[0].read_bytes()


def run_cli() -> None:
    for cls in get_all_schema_classes():
        type_field = cls.model_fields.get("type")
        card_type = type_field.default if type_field else "unknown"
        card = EXAMPLE_CARDS.get(card_type)
        if card is None:
            print(f"[SKIP] {card_type}: no example card defined in EXAMPLE_CARDS")
            continue
        for template in cls.templates:
            data = _render_to_png_bytes(card, template, card_size="A6")
            print(f"[OK]   {card_type} / {template}: {len(data):,} bytes")


def run_streamlit() -> None:
    import streamlit as st

    st.title("Render Templates")
    st.caption("Card dict + Jinja2 template → PDF → PNG")

    card_size = st.radio("Card size", ["A6", "A5"], horizontal=True)

    if not SAMPLE_IMAGE.exists():
        st.info(
            f"No sample image at `{SAMPLE_IMAGE.relative_to(ROOT)}`. "
            "Cards render with a text placeholder instead of a photo. "
            "Drop any PNG there to test image rendering."
        )

    for cls in get_all_schema_classes():
        type_field = cls.model_fields.get("type")
        card_type = type_field.default if type_field else "unknown"

        st.subheader(f"`{card_type}` — {cls.__name__}")

        card = EXAMPLE_CARDS.get(card_type)
        if card is None:
            st.warning(
                f"No example card defined for `{card_type}` in `EXAMPLE_CARDS`. "
                "Add one to this file to see it rendered."
            )
            continue

        cols = st.columns(len(cls.templates))
        for col, template in zip(cols, cls.templates):
            with col:
                st.caption(f"`{template}`")
                with st.spinner("Rendering…"):
                    png_bytes = _render_to_png_bytes(card, template, card_size=card_size)
                st.image(png_bytes)


if in_streamlit():
    run_streamlit()
else:
    run_cli()
