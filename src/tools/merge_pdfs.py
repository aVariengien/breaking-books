"""Assemble individual card PDFs into a single printable sheet."""

from pathlib import Path
from typing import Literal


def merge_pdfs_to_print(
    pdf_paths: list[Path],
    output_path: Path,
    layout: Literal["2up", "4up"] = "2up",
) -> Path:
    """
    Combine individual card PDFs into a printable sheet.

    - "2up": two A6 cards per A4 landscape page.
    - "4up": four A6 cards per A4 landscape page.

    Returns the path to the combined PDF.
    """
    raise NotImplementedError()
