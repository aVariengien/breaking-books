"""Assemble individual card PDFs into a single printable sheet."""

from pathlib import Path
from typing import Literal

from pypdf import PdfReader, PdfWriter

# A4 landscape dimensions in PDF points (1 pt = 1/72 inch)
_A4_W = 841.890
_A4_H = 595.276


def merge_pdfs_to_print(
    pdf_paths: list[Path],
    output_path: Path,
    layout: Literal["2up", "4up"] = "2up",
) -> Path:
    """
    Combine individual card PDFs into a printable sheet.

    - "2up": two cards side by side on an A4 landscape page.
    - "4up": four cards in a 2×2 grid on an A4 landscape page.

    Card size is auto-detected from the first PDF; scaling is applied if
    needed so the cards fit on the sheet.

    Returns the path to the combined PDF.
    """
    if not pdf_paths:
        raise ValueError("No PDF paths provided")

    first_page = PdfReader(str(pdf_paths[0])).pages[0]
    card_w = float(first_page.mediabox.width)
    card_h = float(first_page.mediabox.height)

    writer = PdfWriter()
    if layout == "2up":
        _layout_2up(writer, pdf_paths, card_w, card_h)
    else:
        _layout_4up(writer, pdf_paths, card_w, card_h)

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


def _layout_2up(writer: PdfWriter, pdf_paths: list[Path], card_w: float, card_h: float) -> None:
    """Two cards side by side, centered on an A4 landscape page."""
    gap = 5.0  # points between cards
    scale = min((_A4_W - gap) / (2 * card_w), _A4_H / card_h, 1.0)
    eff_w = card_w * scale
    eff_h = card_h * scale
    left_margin = (_A4_W - 2 * eff_w - gap) / 2
    bottom_margin = (_A4_H - eff_h) / 2

    for i in range(0, len(pdf_paths), 2):
        sheet = writer.add_blank_page(width=_A4_W, height=_A4_H)
        p1 = _read_first_page(pdf_paths[i])
        if p1:
            sheet.merge_transformed_page(p1, (scale, 0, 0, scale, left_margin, bottom_margin))
        if i + 1 < len(pdf_paths):
            p2 = _read_first_page(pdf_paths[i + 1])
            if p2:
                x = left_margin + eff_w + gap
                sheet.merge_transformed_page(p2, (scale, 0, 0, scale, x, bottom_margin))


def _layout_4up(writer: PdfWriter, pdf_paths: list[Path], card_w: float, card_h: float) -> None:
    """Four cards in a 2×2 grid, centered on an A4 landscape page."""
    h_gap = 5.0
    v_gap = 5.0
    scale = min((_A4_W - h_gap) / (2 * card_w), (_A4_H - v_gap) / (2 * card_h), 1.0)
    eff_w = card_w * scale
    eff_h = card_h * scale
    left_margin = (_A4_W - 2 * eff_w - h_gap) / 2
    bottom_margin = (_A4_H - 2 * eff_h - v_gap) / 2

    # (x, y) positions: top-left, top-right, bottom-left, bottom-right
    positions = [
        (left_margin, bottom_margin + eff_h + v_gap),
        (left_margin + eff_w + h_gap, bottom_margin + eff_h + v_gap),
        (left_margin, bottom_margin),
        (left_margin + eff_w + h_gap, bottom_margin),
    ]

    for i in range(0, len(pdf_paths), 4):
        sheet = writer.add_blank_page(width=_A4_W, height=_A4_H)
        for j, pdf_path in enumerate(pdf_paths[i : i + 4]):
            p = _read_first_page(pdf_path)
            if p:
                x, y = positions[j]
                sheet.merge_transformed_page(p, (scale, 0, 0, scale, x, y))
