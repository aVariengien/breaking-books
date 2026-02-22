"""Quality test: merge_pdfs_to_print — card PDFs → printable sheet.

Renders N sample cards and merges them into an A4 landscape sheet.
Layout is derived from card size: A6 → 4 per page, A5 → 2 per page.
Portrait cards are rotated to fit when needed.

CLI:      python quality_tests/pages/4_Merge_PDFs.py
Streamlit: make quality-tests → "Merge PDFs" page
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from lib.models import SectionTheme, VisualIdentity  # noqa: E402
from lib.streamlit_utils import in_streamlit  # noqa: E402
from tools.merge_pdfs import merge_pdfs_to_print  # noqa: E402
from tools.pdf_to_pngs import pdf_to_pngs  # noqa: E402
from tools.render_template import render_card_to_pdf  # noqa: E402

_TITLES = [
    "The Ratchet Effect",
    "Social Learning",
    "Cumulative Culture",
    "Imitation vs. Innovation",
]
_DESCRIPTIONS = [
    "Innovations persist and accumulate. Each generation inherits the last.",
    "We copy the successful, not just the familiar. Learning is deeply social.",
    "Culture accumulates like a ratchet — only forward. No other species does this.",
    "Imitation is cheap; innovation is costly. Most behaviour is copied.",
]
_VI = VisualIdentity(
    title_font="EB Garamond",
    body_font="Lora",
    section_themes=[
        SectionTheme(main_color="#1a1a1a", dark_color="#000000", accent_color="#FF6B6B")
    ],
)


def _make_sample_cards(n: int, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    images_dir = out_dir / "images"
    pdfs = []
    for i in range(n):
        card = {
            "type": "default",
            "section": i // 2,
            "title": _TITLES[i % len(_TITLES)],
            "description": _DESCRIPTIONS[i % len(_DESCRIPTIONS)],
            "illustration": f"Evocative scene for concept {i + 1}.",
            "illustration_style": "Minimal, editorial.",
            "quote": "A short quote from the book that illustrates the concept.",
        }
        pdfs.append(
            render_card_to_pdf(
                card,
                "default-classic.html.jinja2",
                out_dir,
                images_dir,
                card_index=i,
                visual_identity=_VI,
            )
        )
    return pdfs


def run_cli() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        pdfs = _make_sample_cards(4, tmp_dir / "cards")
        for card_size in ["A6", "A5"]:
            out = tmp_dir / f"merged_{card_size}.pdf"
            result = merge_pdfs_to_print(pdfs, out, card_size=card_size)
            layout = "4-up" if card_size == "A6" else "2-up"
            print(f"{card_size} ({layout}): {result.stat().st_size:,} bytes")


def run_streamlit() -> None:
    import streamlit as st

    st.title("Merge PDFs")
    st.caption(
        "Card PDFs → A4 landscape sheet. A6 = 4 per page, A5 = 2 per page. Portrait cards rotate to fit."
    )

    col1, col2 = st.columns(2)
    card_size = col1.radio("Card size", ["A6", "A5"], horizontal=True)
    n_cards = col2.slider("Cards", min_value=1, max_value=8, value=4)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with st.spinner(f"Rendering {n_cards} sample cards…"):
            pdfs = _make_sample_cards(n_cards, tmp_dir / "cards")
        layout = "4-up" if card_size == "A6" else "2-up"
        with st.spinner(f"Merging into {layout} layout…"):
            merged = merge_pdfs_to_print(pdfs, tmp_dir / "merged.pdf", card_size=card_size)
        with st.spinner("Converting merged PDF to PNG for preview…"):
            pngs = pdf_to_pngs(merged, tmp_dir / "preview", dpi=150)
        sheet_data = [(p.name, p.stat().st_size, p.read_bytes()) for p in pngs]

    st.metric("Output sheets", len(sheet_data))
    for name, size, data in sheet_data:
        st.caption(f"`{name}` — {size:,} bytes")
        st.image(data)


if in_streamlit():
    run_streamlit()
else:
    run_cli()
