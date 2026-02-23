"""Dev: render_template — card schema + Jinja2 template → PDF → PNG."""

from pathlib import Path

import streamlit as st

from lib.constants import IMAGE_CACHE_DIR, QUALITY_TEST_RENDERS_DIR
from lib.example_cards import build_example_cards
from lib.models import SectionTheme, VisualIdentity
from lib.registry import get_all_schema_classes, get_templates_for_schema
from tools.pdf_to_pngs import pdf_to_pngs
from tools.render_template import (
    PREDEFINED_STYLES,
    render_one_template,
)

EXAMPLE_CARDS: dict[str, dict] = build_example_cards()


def run_streamlit() -> None:
    st.title("Render Templates")
    st.caption("Card dict + Jinja2 template → PDF → PNG (using predefined visual identities)")

    style_options = list(PREDEFINED_STYLES.keys()) + ["Custom"]
    style_name = st.radio("Visual identity style", style_options, horizontal=True)

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

    output_dir = QUALITY_TEST_RENDERS_DIR / "streamlit"
    output_dir.mkdir(parents=True, exist_ok=True)

    for cls in get_all_schema_classes():
        type_field = cls.model_fields.get("type")
        card_type = type_field.default if type_field else "unknown"

        st.subheader(f"`{card_type}` — {cls.__name__}")

        card = EXAMPLE_CARDS.get(card_type)
        if card is None:
            st.warning(f"No example card defined for `{card_type}`. Add one to see it rendered.")
            continue

        templates = list(get_templates_for_schema(cls))
        COLS_PER_ROW = 3
        for i in range(0, len(templates), COLS_PER_ROW):
            chunk = templates[i : i + COLS_PER_ROW]
            cols = st.columns(COLS_PER_ROW)
            for col, template_path in zip(cols, chunk):
                with col:
                    template_name = template_path.name
                    st.caption(f"`{template_name}`")
                    with st.spinner("Rendering…"):
                        result = render_one_template(
                            card,
                            card_type,
                            template_name,
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


run_streamlit()
