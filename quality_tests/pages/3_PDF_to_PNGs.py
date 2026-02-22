"""Quality test: pdf_to_pngs — PDF pages → PNG files.

Generates a sample card PDF, then converts it to PNG at a selectable DPI.

CLI:      python quality_tests/pages/3_PDF_to_PNGs.py
Streamlit: make quality-tests → "PDF to PNGs" page
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from lib.example_cards import build_example_cards  # noqa: E402
from lib.font_cache import fetch_and_cache_font_awesome, fetch_and_cache_fonts  # noqa: E402
from lib.streamlit_utils import in_streamlit  # noqa: E402
from tools.pdf_to_pngs import pdf_to_pngs  # noqa: E402
from tools.render_template import (  # noqa: E402
    PREDEFINED_STYLES,
    build_google_fonts_url,
    render_card_to_pdf,
)

_EXAMPLE_CARD = build_example_cards()["default"]


def _make_sample_pdf(tmp_dir: Path) -> Path:
    images_dir = tmp_dir / "images"
    vi = PREDEFINED_STYLES["classic"]
    font_face_css = fetch_and_cache_fonts(build_google_fonts_url(vi, extra_fonts=["EB Garamond"]))
    font_awesome_css = fetch_and_cache_font_awesome()
    return render_card_to_pdf(
        _EXAMPLE_CARD,
        "default-classic.html.jinja2",
        tmp_dir,
        images_dir,
        card_index=0,
        font_face_css=font_face_css,
        font_awesome_css=font_awesome_css,
        visual_identity=vi.model_dump(),
    )


def run_cli() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        pdf = _make_sample_pdf(tmp_dir)
        print(f"Sample PDF: {pdf.stat().st_size:,} bytes")
        for dpi in [72, 150, 300]:
            pngs = pdf_to_pngs(pdf, tmp_dir / f"pngs_{dpi}", dpi=dpi)
            sizes = [f"{p.stat().st_size:,}" for p in pngs]
            print(f"  DPI {dpi:3d}: {len(pngs)} page(s), sizes: {sizes} bytes")


def run_streamlit() -> None:
    import streamlit as st

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


if in_streamlit():
    run_streamlit()
else:
    run_cli()
