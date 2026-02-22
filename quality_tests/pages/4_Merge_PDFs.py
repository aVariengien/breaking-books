"""Quality test: merge_pdfs_to_print — card PDFs → printable sheet.

Renders N sample cards (from schema get_examples(), like Render Templates) and
merges them into an A4 landscape sheet. Layout: A6 → 4 per page, A5 → 2 per page.
Portrait cards are rotated to fit when needed.

CLI:      python quality_tests/pages/4_Merge_PDFs.py
Streamlit: make quality-tests → "Merge PDFs" page
"""

import sys
import tempfile
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from lib.example_cards import build_example_cards  # noqa: E402
from lib.font_cache import fetch_and_cache_font_awesome, fetch_and_cache_fonts  # noqa: E402
from lib.registry import get_all_schema_classes, get_templates_for_schema  # noqa: E402
from lib.streamlit_utils import in_streamlit  # noqa: E402
from tools.merge_pdfs import merge_pdfs_to_print  # noqa: E402
from tools.pdf_to_pngs import pdf_to_pngs  # noqa: E402
from tools.render_template import (  # noqa: E402
    PREDEFINED_STYLES,
    build_google_fonts_url,
    render_card_to_pdf,
)

EXAMPLE_CARDS = build_example_cards()
_IMAGE_CACHE_DIR = ROOT / "data" / "image_cache"


def _card_type_and_template_pairs() -> list[tuple[str, str]]:
    """Return (card_type, template_name) for each schema with an example."""
    pairs: list[tuple[str, str]] = []
    for cls in get_all_schema_classes():
        type_field = cls.model_fields.get("type")
        card_type = type_field.default if type_field else None
        if card_type is None or card_type not in EXAMPLE_CARDS:
            continue
        templates = get_templates_for_schema(cls)
        if templates:
            pairs.append((card_type, templates[0].name))
    return pairs


_CARD_TEMPLATE_PAIRS = _card_type_and_template_pairs()


def _make_sample_cards(n: int, out_dir: Path) -> list[Path]:
    """Render n cards cycling through example cards (same source as Render Templates)."""
    if not _CARD_TEMPLATE_PAIRS:
        raise ValueError("No example cards available; add get_examples() to schemas")
    out_dir.mkdir(parents=True, exist_ok=True)
    _IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    vi = PREDEFINED_STYLES["classic"]
    font_face_css = fetch_and_cache_fonts(build_google_fonts_url(vi, extra_fonts=["EB Garamond"]))
    font_awesome_css = fetch_and_cache_font_awesome()
    pdfs = []
    for i in range(n):
        card_type, template_name = _CARD_TEMPLATE_PAIRS[i % len(_CARD_TEMPLATE_PAIRS)]
        card = EXAMPLE_CARDS[card_type].copy()
        card["section"] = i % 3  # Vary section for theme variety
        pdfs.append(
            render_card_to_pdf(
                card,
                template_name,
                out_dir,
                _IMAGE_CACHE_DIR,
                card_index=i,
                font_face_css=font_face_css,
                font_awesome_css=font_awesome_css,
                visual_identity=vi.model_dump(),
            )
        )
    return pdfs


@st.cache_data(show_spinner="Rendering sample cards…")
def _get_cached_sample_card_pdfs(n: int) -> list[bytes]:
    """Render n sample cards and return their PDF bytes. Cached per n."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        out_dir = tmp_dir / "cards"
        paths = _make_sample_cards(n, out_dir)
        return [p.read_bytes() for p in paths]


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

    pdf_bytes_list = _get_cached_sample_card_pdfs(n_cards)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        card_dir = tmp_dir / "cards"
        card_dir.mkdir()
        pdfs = []
        for i, data in enumerate(pdf_bytes_list):
            p = card_dir / f"card_{i}.pdf"
            p.write_bytes(data)
            pdfs.append(p)
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
