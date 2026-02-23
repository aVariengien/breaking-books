"""Dev: pdf_to_pngs — PDF pages → PNG files."""

import tempfile
from pathlib import Path

import streamlit as st

from lib.example_cards import build_example_cards
from tools.pdf_to_pngs import pdf_to_pngs
from tools.render_template import PREDEFINED_STYLES, render_card_to_pdf

_EXAMPLE_CARD = build_example_cards()["default"]


def _make_sample_pdf(tmp_dir: Path) -> Path:
    images_dir = tmp_dir / "images"
    return render_card_to_pdf(
        _EXAMPLE_CARD,
        "default-classic.html.jinja2",
        tmp_dir,
        images_dir,
        card_index=0,
        visual_identity=PREDEFINED_STYLES["classic"].model_dump(),
    )


def run_streamlit() -> None:
    st.title("PDF to PNGs")
    st.caption("PDF → PNG conversion used by QC visual review")

    dpi = st.slider("DPI", min_value=72, max_value=300, value=150, step=1)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with st.spinner("Rendering sample card…"):
            pdf = _make_sample_pdf(tmp_dir)
        with st.spinner(f"Converting to PNG at {dpi} DPI…"):
            pngs = pdf_to_pngs(pdf, tmp_dir / "pngs", dpi=dpi)
        png_data = [(p.name, p.stat().st_size, p.read_bytes()) for p in pngs]

    st.metric("Pages converted", len(png_data))
    for name, size, data in png_data:
        st.caption(f"`{name}` — {size:,} bytes")
        st.image(data)


run_streamlit()
