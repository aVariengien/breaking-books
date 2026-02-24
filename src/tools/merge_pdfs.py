"""Assemble individual card PDFs into a single printable sheet."""

from pathlib import Path
from typing import Literal

from pypdf import PdfReader, PdfWriter, Transformation

# A4 dimensions in PDF points (1 pt = 1/72 inch)
_A4_PORTRAIT_W = 595.276
_A4_PORTRAIT_H = 841.890
# A4 landscape (used by 2-up layout)
_A4_W = 841.890
_A4_H = 595.276

_GAP = 5.0


def merge_pdfs_to_print(
    pdf_paths: list[Path],
    output_path: Path,
    card_size: Literal["A5", "A6"],
) -> Path:
    """
    Combine individual card PDFs into a printable sheet.

    Layout is derived from card_size:
    - A6: 4 cards per page (2×2 grid), rotating portrait cards to fit.
    - A5: 2 cards per page (no rotation needed).

    Cards are placed on A4 landscape sheets. Scaling and rotation are applied
    so cards fit optimally.

    Returns the path to the combined PDF.
    """
    if not pdf_paths:
        raise ValueError("No PDF paths provided")

    layout: Literal["2up", "4up"] = "4up" if card_size == "A6" else "2up"

    writer = PdfWriter()
    if layout == "2up":
        _layout_2up(writer, pdf_paths)
    else:
        _layout_4up(writer, pdf_paths)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as fp:
        writer.write(fp)
    return output_path


def _read_first_page(pdf_path: Path):
    """Return the first page of a PDF, or None on error."""
    try:
        reader = PdfReader(str(pdf_path))
        return reader.pages[0] if reader.pages else None
    except Exception:
        return None


def _get_page_size(page) -> tuple[float, float]:
    """Return (width, height) of the page."""
    w = float(page.mediabox.width)
    h = float(page.mediabox.height)
    return (w, h)


def _is_portrait(w: float, h: float) -> bool:
    """True if page is portrait (height > width)."""
    return h > w


def _layout_2up(writer: PdfWriter, pdf_paths: list[Path]) -> None:
    """Two cards per page. Both portrait and landscape fit without rotation."""
    cards_per_page = 2
    slot_w = (_A4_W - _GAP) / 2
    slot_h = _A4_H

    for i in range(0, len(pdf_paths), cards_per_page):
        sheet = writer.add_blank_page(width=_A4_W, height=_A4_H)
        for j, pdf_path in enumerate(pdf_paths[i : i + cards_per_page]):
            p = _read_first_page(pdf_path)
            if not p:
                continue
            w, h = _get_page_size(p)
            scale = min(slot_w / w, slot_h / h)  # scale up to fill A5 slot when card is A6
            eff_w, eff_h = w * scale, h * scale
            x = j * (slot_w + _GAP) + (slot_w - eff_w) / 2
            y = (slot_h - eff_h) / 2
            sheet.merge_transformed_page(p, (scale, 0, 0, scale, x, y))


def _layout_4up(writer: PdfWriter, pdf_paths: list[Path]) -> None:
    """Four cards per page (2×2) on A4 portrait. Portrait A6 cards fit without rotation."""
    cards_per_page = 4
    slot_w = (_A4_PORTRAIT_W - _GAP) / 2
    slot_h = (_A4_PORTRAIT_H - _GAP) / 2

    positions = [
        (0, 1),  # top-left
        (1, 1),  # top-right
        (0, 0),  # bottom-left
        (1, 0),  # bottom-right
    ]

    for i in range(0, len(pdf_paths), cards_per_page):
        sheet = writer.add_blank_page(width=_A4_PORTRAIT_W, height=_A4_PORTRAIT_H)
        for j, pdf_path in enumerate(pdf_paths[i : i + cards_per_page]):
            p = _read_first_page(pdf_path)
            if not p:
                continue
            w, h = _get_page_size(p)
            # Landscape cards are rotated to fit portrait slots; portrait cards stay as-is
            rotate = not _is_portrait(w, h)
            if rotate:
                eff_w, eff_h = h, w
            else:
                eff_w, eff_h = w, h
            scale = min(slot_w / eff_w, slot_h / eff_h, 1.0)
            eff_w, eff_h = eff_w * scale, eff_h * scale
            col, row = positions[j]
            x = col * (slot_w + _GAP) + (slot_w - eff_w) / 2
            y = row * (slot_h + _GAP) + (slot_h - eff_h) / 2

            if rotate:
                # Rotate around page center so content stays in predictable coordinates
                slot_left = col * (slot_w + _GAP)
                slot_bottom = row * (slot_h + _GAP)
                cx = slot_left + slot_w / 2
                cy = slot_bottom + slot_h / 2
                t = (
                    Transformation()
                    .translate(tx=-w / 2, ty=-h / 2)
                    .rotate(90)
                    .scale(sx=scale, sy=scale)
                    .translate(tx=cx, ty=cy)
                )
                sheet.merge_transformed_page(p, t.ctm)
            else:
                sheet.merge_transformed_page(p, (scale, 0, 0, scale, x, y))
