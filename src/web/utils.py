"""Shared utilities and reusable UI components for the Breaking Books web app."""

import io
import tempfile
import zipfile
from pathlib import Path
from typing import Literal

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer

from tools.merge_pdfs import merge_pdfs_to_print
from tools.pdf_to_pngs import pdf_to_pngs
from tools.render_template import cards_json_to_pdfs

_IMAGE_CACHE_DIR = Path(__file__).parents[2] / "data" / "image_cache"


# ---------------------------------------------------------------------------
# Render Deck component
# ---------------------------------------------------------------------------


def render_deck_ui(
    cards_json_bytes: bytes,
    *,
    key_prefix: str = "deck",
) -> None:
    """
    Full render-deck UI component.

    Accepts a cards.json as raw bytes. Shows card-size selector immediately,
    then on "Render" renders all cards, merges to a printable PDF, displays it
    inline via pdf_viewer, and provides download buttons (PDF + card PNGs ZIP).

    `key_prefix` namespaces all widget keys for safe multi-instance embedding.
    """
    import json

    try:
        json.loads(cards_json_bytes)
    except json.JSONDecodeError as exc:
        st.error(f"Invalid JSON: {exc}")
        return

    card_size: Literal["A6", "A5"] = st.radio(  # type: ignore[assignment]
        "Card size",
        ["A6", "A5"],
        horizontal=True,
        key=f"{key_prefix}_card_size",
        help="A6 → 4 cards per A4 sheet · A5 → 2 cards per A4 sheet",
    )

    if st.button("Render deck", type="primary", key=f"{key_prefix}_render_btn"):
        _do_render(
            cards_json_bytes=cards_json_bytes,
            card_size=card_size,
            key_prefix=key_prefix,
        )


def _do_render(
    *,
    cards_json_bytes: bytes,
    card_size: Literal["A6", "A5"],
    key_prefix: str,
) -> None:
    _IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        cards_json_path = tmp_dir / "cards.json"
        cards_json_path.write_bytes(cards_json_bytes)

        renders_dir = tmp_dir / "renders"
        merged_path = tmp_dir / "deck.pdf"

        with st.status("Rendering…", expanded=True) as status:
            st.write("Rendering cards…")
            pdf_paths = cards_json_to_pdfs(
                cards_json_path,
                renders_dir,
                _IMAGE_CACHE_DIR,
            )
            st.write(f"{len(pdf_paths)} cards rendered.")
            st.write("Merging into print sheet…")
            merge_pdfs_to_print(pdf_paths, merged_path, card_size=card_size)
            status.update(label="Done.", state="complete", expanded=False)

        merged_pdf_bytes = merged_path.read_bytes()
        card_png_pairs = _card_pdfs_to_pngs(pdf_paths, tmp_dir / "card_pngs")

    st.divider()

    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "Download PDF",
            data=merged_pdf_bytes,
            file_name="deck.pdf",
            mime="application/pdf",
            type="primary",
            key=f"{key_prefix}_dl_pdf",
        )
    with dl_col2:
        st.download_button(
            "Download card PNGs (ZIP)",
            data=_build_zip(card_png_pairs),
            file_name="deck_cards.zip",
            mime="application/zip",
            key=f"{key_prefix}_dl_zip",
        )

    pdf_viewer(merged_pdf_bytes, key=f"{key_prefix}_viewer")


def _card_pdfs_to_pngs(
    pdf_paths: list[Path],
    output_dir: Path,
    dpi: int = 150,
) -> list[tuple[str, bytes]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pairs: list[tuple[str, bytes]] = []
    for i, pdf_path in enumerate(sorted(pdf_paths, key=lambda p: p.stem)):
        png_dir = output_dir / f"{i:04d}"
        pngs = pdf_to_pngs(pdf_path, png_dir, dpi=dpi)
        if pngs:
            pairs.append((f"card_{i + 1:04d}.png", pngs[0].read_bytes()))
    return pairs


def _build_zip(pairs: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in pairs:
            zf.writestr(f"cards/{name}", data)
    return buf.getvalue()
