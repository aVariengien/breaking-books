"""Quality test: render_template — card schema + Jinja2 template → PDF → PNG.

Renders one card per schema type × template using hardcoded example data
and predefined visual identities (no LLM required).

All cards render at A6 size. Image generation uses cached images; otherwise
cards render with a text placeholder.

CLI:      python quality_tests/pages/2_Render_Templates.py
Streamlit: make quality-tests → "Render Templates" page
"""

import json
import logging
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


class _LogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _render_to_png_bytes(
    card: dict,
    template_name: str,
    visual_identity: dict | None = None,
    dpi: int = 150,
) -> tuple[bytes, list[logging.LogRecord]]:
    """
    Render a card dict to PNG bytes (single-page card assumed).

    Returns (png_bytes, weasyprint_log_records).
    """
    if visual_identity is None:
        visual_identity = PREDEFINED_STYLES["classic"].model_dump()

    capture = _LogCapture()
    wp_logger = logging.getLogger("weasyprint")
    wp_logger.addHandler(capture)
    try:
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
            return pngs[0].read_bytes(), capture.records
    finally:
        wp_logger.removeHandler(capture)


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
    from lib.models import VisualIdentity, SectionTheme

    st.set_page_config(layout="wide")
    st.title("Render Templates")
    st.caption("Card dict + Jinja2 template → PDF → PNG (using predefined visual identities)")

    # Select style: predefined or custom
    style_options = list(PREDEFINED_STYLES.keys()) + ["Custom"]
    style_name = st.radio(
        "Visual identity style",
        style_options,
        horizontal=True,
    )

    if style_name == "Custom":
        col1, col2 = st.columns(2)
        with col1:
            description = st.text_input("Description", value="Custom visual identity")
            title_font = st.text_input("Title font", value="EB Garamond")
        with col2:
            body_font = st.text_input("Body font", value="Lora")

        st.write("**Section theme colors:**")
        color_cols = st.columns(3)
        with color_cols[0]:
            main_color = st.color_picker("Main color", "#1a1a1a")
        with color_cols[1]:
            dark_color = st.color_picker("Dark color", "#000000")
        with color_cols[2]:
            accent_color = st.color_picker("Accent color", "#FF6B6B")

        vi_obj = VisualIdentity(
            description=description,
            title_font=title_font,
            body_font=body_font,
            section_themes=[
                SectionTheme(
                    main_color=main_color, dark_color=dark_color, accent_color=accent_color
                )
            ],
        )
        selected_style = vi_obj.model_dump()
    else:
        vi_obj = PREDEFINED_STYLES[style_name]
        selected_style = vi_obj.model_dump()

        # Display predefined style details
        st.write(f"**{vi_obj.description}**")

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Title font:** {vi_obj.title_font}")
            st.write(f"**Body font:** {vi_obj.body_font}")

        with col2:
            if vi_obj.section_themes:
                theme = vi_obj.section_themes[0]
                st.write("**Colors:**")
                color_cols = st.columns(3)
                with color_cols[0]:
                    st.color_picker(
                        "Main color preview",
                        theme.main_color,
                        disabled=True,
                        label_visibility="collapsed",
                    )
                    st.caption("Main")
                with color_cols[1]:
                    st.color_picker(
                        "Dark color preview",
                        theme.dark_color,
                        disabled=True,
                        label_visibility="collapsed",
                    )
                    st.caption("Dark")
                with color_cols[2]:
                    st.color_picker(
                        "Accent color preview",
                        theme.accent_color,
                        disabled=True,
                        label_visibility="collapsed",
                    )
                    st.caption("Accent")

    st.divider()

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
        def _cached_render(
            card_json: str, template_name: str, style_json: str
        ) -> tuple[bytes, list[str]] | str:
            try:
                png_bytes, records = _render_to_png_bytes(
                    json.loads(card_json),
                    template_name,
                    visual_identity=json.loads(style_json),
                )
                warnings = [r.getMessage() for r in records if r.levelno >= logging.WARNING]
                return png_bytes, warnings
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
                    if isinstance(result, str):
                        st.warning(result)
                    else:
                        png_bytes, warnings = result
                        st.image(png_bytes)
                        for w in warnings:
                            st.warning(w)


if in_streamlit():
    run_streamlit()
else:
    run_cli()
