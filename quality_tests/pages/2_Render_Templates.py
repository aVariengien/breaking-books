"""Quality test: render_template — card schema + Jinja2 template → PDF → PNG.

Renders one card per schema type × template using hardcoded example data
and predefined visual identities (no LLM required).

All cards render at A6 size. Image generation uses cached images; otherwise
cards render with a text placeholder.

CLI:      python quality_tests/pages/2_Render_Templates.py
Streamlit: make quality-tests → "Render Templates" page
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from lib.registry import get_all_schema_classes  # noqa: E402
from lib.streamlit_utils import in_streamlit  # noqa: E402
from tools.pdf_to_pngs import pdf_to_pngs  # noqa: E402
from tools.render_template import PREDEFINED_STYLES, render_card_to_pdf  # noqa: E402

_TEMPLATES_DIR = ROOT / "src" / "templates"
_IMAGE_CACHE_DIR = ROOT / "data" / "image_cache"


# ---------------------------------------------------------------------------
# Example cards — built from each schema's get_examples() classmethod.
# ---------------------------------------------------------------------------
def _build_example_cards() -> dict[str, dict]:
    result: dict[str, dict] = {}
    for cls in get_all_schema_classes():
        type_field = cls.model_fields.get("type")
        card_type = type_field.default if type_field else None
        if card_type is None:
            continue
        examples = cls.get_examples()
        if examples:
            result[card_type] = examples[0].model_dump()
    return result


EXAMPLE_CARDS: dict[str, dict] = _build_example_cards()


def _all_templates_for_type(card_type: str, template_glob: str) -> list[str]:
    """
    Find all templates matching the card type's glob pattern.

    template_glob: a glob pattern like "default-*.html.jinja2" or "default.html.jinja2"
    """
    # Expand glob pattern relative to TEMPLATES_DIR
    matching = sorted(p.name for p in _TEMPLATES_DIR.glob(template_glob))
    return matching if matching else []


def _render_to_png_bytes(
    card: dict,
    template_name: str,
    visual_identity: dict | None = None,
    dpi: int = 150,
) -> bytes:
    """
    Render a card dict to PNG bytes (single-page card assumed).

    - card: card data dict
    - template_name: Jinja2 template filename
    - visual_identity: optional VisualIdentity dict (uses PREDEFINED_STYLES['classic'] if None)
    - dpi: DPI for PDF→PNG conversion
    """
    if visual_identity is None:
        visual_identity = PREDEFINED_STYLES["classic"].model_dump()

    _IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        pdf = render_card_to_pdf(
            card,
            template_name,
            tmp_dir,
            _IMAGE_CACHE_DIR,
            card_index=0,
            visual_identity=visual_identity,
        )
        pngs = pdf_to_pngs(pdf, tmp_dir / "pngs", dpi=dpi)
        return pngs[0].read_bytes()


def run_cli() -> None:
    vi_classic = PREDEFINED_STYLES["classic"].model_dump()
    for cls in get_all_schema_classes():
        type_field = cls.model_fields.get("type")
        card_type = type_field.default if type_field else "unknown"
        card = EXAMPLE_CARDS.get(card_type)
        if card is None:
            print(f"[SKIP] {card_type}: no example card defined in EXAMPLE_CARDS")
            continue
        for template in _all_templates_for_type(card_type, cls.templates):
            try:
                data = _render_to_png_bytes(card, template, visual_identity=vi_classic)
                print(f"[OK]   {card_type} / {template}: {len(data):,} bytes")
            except Exception as e:
                print(f"[WARN] {card_type} / {template}: {e}")


def run_streamlit() -> None:
    import streamlit as st

    st.set_page_config(layout="wide")
    st.title("Render Templates")
    st.caption("Card dict + Jinja2 template → PDF → PNG (using predefined visual identities)")

    # Select visual identity style
    style_name = st.radio(
        "Visual identity style",
        list(PREDEFINED_STYLES.keys()),
        horizontal=True,
    )
    selected_style = PREDEFINED_STYLES[style_name].model_dump()

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

        templates = _all_templates_for_type(card_type, cls.templates)

        @st.cache_data(show_spinner=False)
        def _cached_render(card_json: str, template_name: str, style_json: str) -> bytes | str:
            try:
                return _render_to_png_bytes(
                    json.loads(card_json),
                    template_name,
                    visual_identity=json.loads(style_json),
                )
            except Exception as e:
                return f"{type(e).__name__}: {e}"

        card_json = json.dumps(card, sort_keys=True, default=str)
        style_json = json.dumps(selected_style, sort_keys=True, default=str)
        COLS_PER_ROW = 3
        for i in range(0, len(templates), COLS_PER_ROW):
            chunk = templates[i : i + COLS_PER_ROW]
            cols = st.columns(COLS_PER_ROW)
            for col, template in zip(cols, chunk):
                with col:
                    st.caption(f"`{template}`")
                    with st.spinner("Rendering…"):
                        result = _cached_render(card_json, template, style_json)
                    if isinstance(result, bytes):
                        st.image(result)
                    else:
                        st.warning(result)


if in_streamlit():
    run_streamlit()
else:
    run_cli()
