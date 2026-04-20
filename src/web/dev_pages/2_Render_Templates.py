"""Dev: render_template — card schema + Jinja2 template → PDF → PNG."""

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from lib.constants import IMAGE_CACHE_DIR, QUALITY_TEST_RENDERS_DIR, TEMPLATES_DIR
from lib.example_cards import build_example_cards
from lib.models import SectionTheme, VisualIdentity
from lib.registry import get_all_schema_classes, get_templates_for_schema
from tools.pdf_to_pngs import pdf_to_pngs
from tools.render_template import (
    PREDEFINED_STYLES,
    render_card_to_html,
    render_one_template,
)

EXAMPLE_CARDS: dict[str, dict] = build_example_cards()


def _build_template_to_card_type() -> dict[str, str]:
    """Map template filename → card_type string."""
    result: dict[str, str] = {}
    for cls in get_all_schema_classes():
        type_field = cls.model_fields.get("type")
        card_type = type_field.default if type_field else "unknown"
        for tpl_path in get_templates_for_schema(cls):
            result[tpl_path.name] = card_type
    return result


def visual_identity_selector(key_prefix: str = "") -> dict:
    style_options = list(PREDEFINED_STYLES.keys()) + ["Custom"]
    style_name = st.radio(
        "Visual identity style", style_options, horizontal=True, key=f"{key_prefix}style"
    )

    if style_name == "Custom":
        col1, col2 = st.columns(2)
        with col1:
            description = st.text_input(
                "Description", value="Custom visual identity", key=f"{key_prefix}desc"
            )
            title_font = st.text_input("Title font", value="EB Garamond", key=f"{key_prefix}tfont")
        with col2:
            body_font = st.text_input("Body font", value="Lora", key=f"{key_prefix}bfont")

        st.write("**Section theme colors:**")
        color_cols = st.columns(3)
        with color_cols[0]:
            main_color = st.color_picker("Main color", "#8B1E3F", key=f"{key_prefix}main")
        with color_cols[1]:
            dark_color = st.color_picker("Dark color", "#1a1a1a", key=f"{key_prefix}dark")
        with color_cols[2]:
            accent_color = st.color_picker("Accent color", "#C97B45", key=f"{key_prefix}accent")

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
        return vi_obj.model_dump()
    else:
        vi_obj = PREDEFINED_STYLES[style_name]
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
                        "Main",
                        theme.main_color,
                        disabled=True,
                        label_visibility="collapsed",
                        key=f"{key_prefix}pmain",
                    )
                    st.caption("Main")
                with color_cols[1]:
                    st.color_picker(
                        "Dark",
                        theme.dark_color,
                        disabled=True,
                        label_visibility="collapsed",
                        key=f"{key_prefix}pdark",
                    )
                    st.caption("Dark")
                with color_cols[2]:
                    st.color_picker(
                        "Accent",
                        theme.accent_color,
                        disabled=True,
                        label_visibility="collapsed",
                        key=f"{key_prefix}paccent",
                    )
                    st.caption("Accent")
        return vi_obj.model_dump()


def run_streamlit() -> None:
    st.title("Render Templates")
    st.caption("Card dict + Jinja2 template → PDF → PNG (using predefined visual identities)")

    tpl_to_type = _build_template_to_card_type()
    all_templates = sorted(
        [p.name for p in TEMPLATES_DIR.glob("*.html.jinja2") if not p.name.startswith("_")]
    )
    ALL = "— All templates —"

    with st.sidebar:
        template_name = st.selectbox("Template", [ALL] + all_templates)
        selected_style = visual_identity_selector(key_prefix="vi_")

    if template_name == ALL:
        output_dir = QUALITY_TEST_RENDERS_DIR / "streamlit"
        output_dir.mkdir(parents=True, exist_ok=True)

        for cls in get_all_schema_classes():
            type_field = cls.model_fields.get("type")
            card_type = type_field.default if type_field else "unknown"

            st.subheader(f"`{card_type}` — {cls.__name__}")

            card = EXAMPLE_CARDS.get(card_type)
            if card is None:
                st.warning(
                    f"No example card defined for `{card_type}`. Add one to see it rendered."
                )
                continue

            templates = list(get_templates_for_schema(cls))
            COLS_PER_ROW = 3
            for i in range(0, len(templates), COLS_PER_ROW):
                chunk = templates[i : i + COLS_PER_ROW]
                cols = st.columns(COLS_PER_ROW)
                for col, template_path in zip(cols, chunk):
                    with col:
                        tpl = template_path.name
                        st.caption(f"`{tpl}`")
                        with st.spinner("Rendering…"):
                            result = render_one_template(
                                card,
                                card_type,
                                tpl,
                                template_path.stem,
                                output_dir,
                                IMAGE_CACHE_DIR,
                                selected_style,
                            )
                            png_dir = (
                                output_dir
                                / "pngs"
                                / f"{result.card_type}_{Path(result.template_name).stem}"
                            )
                            pngs = pdf_to_pngs(result.pdf_path, png_dir, dpi=150)
                            png_bytes = pngs[0].read_bytes() if pngs else b""
                        st.image(png_bytes)
                        for w in result.warnings:
                            st.warning(w)
    else:
        card_type = tpl_to_type.get(template_name, "unknown")

        with st.sidebar:
            st.caption(f"Card type: `{card_type}`")
            output_mode = st.radio(
                "Output", ["PDF → PNG", "HTML"], horizontal=True, key="output_mode"
            )
            default_card = EXAMPLE_CARDS.get(card_type, {"type": card_type})
            card_json = st.text_area(
                "Card data (JSON)",
                value=json.dumps(default_card, indent=2),
                height=300,
                key=f"card_json_{template_name}",
            )

        try:
            card = json.loads(card_json)
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")
            return

        output_dir = QUALITY_TEST_RENDERS_DIR / "streamlit_single"
        output_dir.mkdir(parents=True, exist_ok=True)

        if output_mode == "HTML":
            with st.spinner("Rendering HTML…"):
                try:
                    html = render_card_to_html(
                        card, template_name, IMAGE_CACHE_DIR, visual_identity=selected_style
                    )
                    components.html(html, height=700, scrolling=True)
                except Exception as e:
                    st.error(f"Render error: {e}")
        else:
            with st.spinner("Rendering PDF → PNG…"):
                try:
                    template_stem = Path(template_name).stem
                    result = render_one_template(
                        card,
                        card_type,
                        template_name,
                        template_stem,
                        output_dir,
                        IMAGE_CACHE_DIR,
                        selected_style,
                    )
                    png_dir = output_dir / "pngs" / template_stem
                    pngs = pdf_to_pngs(result.pdf_path, png_dir, dpi=150)
                    png_bytes = pngs[0].read_bytes() if pngs else b""
                    st.image(png_bytes)
                    for w in result.warnings:
                        st.warning(w)
                except Exception as e:
                    st.error(f"Render error: {e}")


run_streamlit()
