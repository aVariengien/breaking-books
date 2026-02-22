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

from lib.example_cards import build_example_cards  # noqa: E402
from lib.registry import get_all_schema_classes, get_templates_for_schema  # noqa: E402
from lib.streamlit_utils import in_streamlit  # noqa: E402
from tools.pdf_to_pngs import pdf_to_pngs  # noqa: E402
from tools.render_template import (  # noqa: E402
    PREDEFINED_STYLES,
    RenderResult,
    render_all_templates,
    render_card_to_pdf,
)

_IMAGE_CACHE_DIR = ROOT / "data" / "image_cache"
_RENDERS_DIR = ROOT / "data" / "quality_test_renders"

EXAMPLE_CARDS: dict[str, dict] = build_example_cards()

_TAG_VALUES: list[str | None] = [None, "top_end", "middle", "bottom_end"]
_TAG_LABELS = [
    "none (standalone)",
    "top_end — first in group",
    "middle",
    "bottom_end — last in group",
]


def _card_with_tag(card: dict, tag: str | None) -> dict:
    return {**card, "tag": tag}


def _results_to_png_lookup(
    results: list[RenderResult], output_dir: Path, dpi: int = 150
) -> dict[tuple[str, str], tuple[bytes, list[str]]]:
    """Convert render results to (card_type, template_name) -> (png_bytes, warnings)."""
    lookup: dict[tuple[str, str], tuple[bytes, list[str]]] = {}
    for r in results:
        png_dir = output_dir / "pngs" / f"{r.card_type}_{Path(r.template_name).stem}"
        pngs = pdf_to_pngs(r.pdf_path, png_dir, dpi=dpi)
        png_bytes = pngs[0].read_bytes() if pngs else b""
        lookup[(r.card_type, r.template_name)] = (png_bytes, r.warnings)
    return lookup


def run_cli() -> None:
    vi_classic = PREDEFINED_STYLES["classic"].model_dump()
    output_dir = _RENDERS_DIR / "cli"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = render_all_templates(output_dir, _IMAGE_CACHE_DIR, vi_classic, EXAMPLE_CARDS)
    lookup = _results_to_png_lookup(results, output_dir)

    for (card_type, template_name), (png_bytes, warnings) in lookup.items():
        status = "[OK]" if not warnings else "[WARN]"
        print(f"{status}   {card_type} / {template_name}: {len(png_bytes):,} bytes")
        for w in warnings:
            print(f"       {w}")

    # Tag system — render one card type with all four tag values
    print("\n--- Tag system ---")
    all_classes = list(get_all_schema_classes())
    demo_cls = next(
        (
            c
            for c in all_classes
            if c.model_fields.get("type") and c.model_fields["type"].default in EXAMPLE_CARDS
        ),
        None,
    )
    if demo_cls:
        demo_type = demo_cls.model_fields["type"].default
        templates = get_templates_for_schema(demo_cls)
        if templates:
            tmpl = templates[0].name
            base_card = EXAMPLE_CARDS[demo_type]
            print(f"Using: {demo_type} / {tmpl}")
            with tempfile.TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                for idx, (tag_val, label) in enumerate(zip(_TAG_VALUES, _TAG_LABELS)):
                    tagged = _card_with_tag(base_card, tag_val)
                    subdir = tmp_dir / f"tag_{idx}"
                    subdir.mkdir()
                    try:
                        pdf = render_card_to_pdf(
                            tagged,
                            tmpl,
                            subdir,
                            _IMAGE_CACHE_DIR,
                            card_index=0,
                            visual_identity=vi_classic,
                        )
                        pngs = pdf_to_pngs(pdf, subdir / "pngs", dpi=150)
                        size = len(pngs[0].read_bytes()) if pngs else 0
                        print(f"[OK]   tag={tag_val!r} ({label}): {size:,} bytes")
                    except Exception as e:
                        print(f"[WARN] tag={tag_val!r} ({label}): {e}")


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

    @st.cache_data(show_spinner="Rendering all templates…")
    def _cached_all_renders(style_json: str) -> dict[tuple[str, str], tuple[bytes, list[str]]]:
        output_dir = _RENDERS_DIR / "streamlit"
        output_dir.mkdir(parents=True, exist_ok=True)
        results = render_all_templates(
            output_dir, _IMAGE_CACHE_DIR, json.loads(style_json), EXAMPLE_CARDS
        )
        return _results_to_png_lookup(results, output_dir)

    style_json = json.dumps(selected_style, sort_keys=True, default=str)
    lookup = _cached_all_renders(style_json)

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

        templates = [p.name for p in get_templates_for_schema(cls)]
        COLS_PER_ROW = 3
        for i in range(0, len(templates), COLS_PER_ROW):
            chunk = templates[i : i + COLS_PER_ROW]
            cols = st.columns(COLS_PER_ROW)
            for col, template in zip(cols, chunk):
                with col:
                    st.caption(f"`{template}`")
                    result = lookup.get((card_type, template))
                    if result is None:
                        st.warning("Not rendered")
                    else:
                        png_bytes, warnings = result
                        st.image(png_bytes)
                        for w in warnings:
                            st.warning(w)


if in_streamlit():
    run_streamlit()
else:
    run_cli()
