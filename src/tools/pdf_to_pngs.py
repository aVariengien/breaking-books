"""Convert PDF pages to PNG files (used by QC visual checks)."""

from pathlib import Path

import pypdfium2 as pdfium


def pdf_to_pngs(pdf_path: Path, output_dir: Path, dpi: int = 150) -> list[Path]:
    """
    Convert each page of a PDF to a PNG file.

    Output files are named `{pdf_stem}-p{page_number:03d}.png`.
    Returns the list of output paths in page order.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(pdf_path))
    scale = dpi / 72  # pdfium renders at 72 DPI by default

    paths: list[Path] = []
    for i, page in enumerate(doc):
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()
        out_path = output_dir / f"{pdf_path.stem}-p{i:03d}.png"
        pil_image.save(str(out_path))
        paths.append(out_path)

    return paths
