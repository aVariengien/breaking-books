"""Quality test: merge_pdfs_to_print — card PDFs → printable sheet.

Renders N sample cards (alternating left/right templates) and merges them
into a 2-up or 4-up A4 landscape sheet.

CLI:      python quality_tests/pages/4_Merge_PDFs.py
Streamlit: make quality-tests → "Merge PDFs" page
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from lib.streamlit_utils import in_streamlit  # noqa: E402
from tools.merge_pdfs import merge_pdfs_to_print  # noqa: E402
from tools.pdf_to_pngs import pdf_to_pngs  # noqa: E402
from tools.render_template import render_card_to_pdf  # noqa: E402

_TITLES = [
    "The Ratchet Effect",
    "Social Learning",
    "Cumulative Culture",
    "Imitation vs. Innovation",
    "Niche Construction",
    "Gene–Culture Coevolution",
    "Theory of Mind",
    "Shared Intentionality",
]
_QUOTES = [
    ["Innovations persist and accumulate.", "Each generation inherits the last."],
    ["We copy the successful, not just the familiar.", "Learning is deeply social."],
    ["Culture accumulates like a ratchet — only forward.", "No other species does this."],
    ["Imitation is cheap; innovation is costly.", "Most behaviour is copied."],
    [
        "Organisms engineer their own selective environment.",
        "Beavers build dams; humans build cities.",
    ],
    ["Genes and culture co-evolve over millennia.", "Lactase persistence is a textbook case."],
    [
        "Knowing that others have minds enables cooperation.",
        "Deception requires a model of belief.",
    ],
    [
        "Shared goals are the foundation of human culture.",
        "Joint attention emerges at nine months.",
    ],
]
_TEMPLATES = ["concept-image-left.html.jinja2", "concept-image-right.html.jinja2"]


def _make_sample_cards(n: int, card_size: str, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    images_dir = out_dir / "images"
    pdfs = []
    for i in range(n):
        card = {
            "type": "concept",
            "section": i // 3,
            "title": _TITLES[i % len(_TITLES)],
            "book_quotes": _QUOTES[i % len(_QUOTES)],
            "image_description": f"Evocative scene for concept {i + 1}.",
            "card_size": card_size,
            "language": "en",
        }
        template = _TEMPLATES[i % len(_TEMPLATES)]
        pdfs.append(render_card_to_pdf(card, template, out_dir, images_dir, card_index=i))
    return pdfs


def run_cli() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for card_size in ["A6", "A5"]:
            pdfs = _make_sample_cards(4, card_size, tmp_dir / card_size / "cards")
            for layout in ["2up", "4up"]:
                out = tmp_dir / card_size / f"merged_{layout}.pdf"
                result = merge_pdfs_to_print(pdfs, out, layout=layout)
                print(f"{card_size} {layout}: {result.stat().st_size:,} bytes")


def run_streamlit() -> None:
    import streamlit as st

    st.title("Merge PDFs")
    st.caption("Card PDFs → printable A4 landscape sheet (2-up / 4-up)")

    col1, col2, col3 = st.columns(3)
    card_size = col1.radio("Card size", ["A6", "A5"], horizontal=True)
    layout = col2.radio("Layout", ["2up", "4up"], horizontal=True)
    n_cards = col3.slider("Cards", min_value=1, max_value=8, value=4)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with st.spinner(f"Rendering {n_cards} sample cards…"):
            pdfs = _make_sample_cards(n_cards, card_size, tmp_dir / "cards")
        with st.spinner(f"Merging into {layout} layout…"):
            merged = merge_pdfs_to_print(pdfs, tmp_dir / "merged.pdf", layout=layout)
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
