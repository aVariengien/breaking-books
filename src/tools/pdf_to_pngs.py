"""Convert PDF pages to PNG files (used by QC visual checks)."""

from pathlib import Path


def pdf_to_pngs(pdf_path: Path, output_dir: Path, dpi: int = 150) -> list[Path]:
    """
    Convert each page of a PDF to a PNG file.

    Output files are named `{pdf_stem}-p{page_number:03d}.png`.
    Returns the list of output paths in page order.
    """
    raise NotImplementedError()
