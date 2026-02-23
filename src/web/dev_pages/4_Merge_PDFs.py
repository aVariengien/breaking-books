"""Dev: merge_pdfs_to_print — card PDFs → printable sheet."""

import tempfile
from pathlib import Path
from typing import Literal

import streamlit as st

from lib.constants import IMAGE_CACHE_DIR
from lib.example_cards import build_example_cards
from lib.registry import get_all_schema_classes, get_templates_for_schema
from tools.merge_pdfs import merge_pdfs_to_print
from tools.pdf_to_pngs import pdf_to_pngs
from tools.render_template import PREDEFINED_STYLES, render_card_to_pdf

EXAMPLE_CARDS = build_example_cards()


def _card_type_and_template_pairs() -> list[tuple[str, str]]:
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
    if not _CARD_TEMPLATE_PAIRS:
        raise ValueError("No example cards available; add get_examples() to schemas")
    out_dir.mkdir(parents=True, exist_ok=True)
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    vi = PREDEFINED_STYLES["classic"].model_dump()
    pdfs = []
    for i in range(n):
        card_type, template_name = _CARD_TEMPLATE_PAIRS[i % len(_CARD_TEMPLATE_PAIRS)]
        card = EXAMPLE_CARDS[card_type].copy()
        card["section"] = i % 3
        pdfs.append(
            render_card_to_pdf(
                card,
                template_name,
                out_dir,
                IMAGE_CACHE_DIR,
                card_index=i,
                visual_identity=vi,
            )
        )
    return pdfs


@st.cache_data(show_spinner="Rendering sample cards…")
def _get_cached_sample_card_pdfs(n: int) -> list[bytes]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        out_dir = tmp_dir / "cards"
        paths = _make_sample_cards(n, out_dir)
        return [p.read_bytes() for p in paths]


def run_streamlit() -> None:
    st.title("Merge PDFs")
    st.caption(
        "Card PDFs → A4 landscape sheet. A6 = 4 per page, A5 = 2 per page. Portrait cards rotate to fit."
    )

    col1, col2 = st.columns(2)
    card_size: Literal["A6", "A5"] = col1.radio("Card size", ["A6", "A5"], horizontal=True)  # type: ignore[assignment]
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


run_streamlit()
