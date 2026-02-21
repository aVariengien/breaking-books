"""Convert an EPUB (or other input format) into clean HTML for LLM consumption."""

from pathlib import Path


def extract_book_content(epub_path: Path) -> str:
    """
    Convert an EPUB file to clean, normalized HTML.

    - Strips footnotes, headers, and page numbers.
    - Normalizes image paths.
    - Adds stable tag IDs for passage extraction.

    Returns the full book as a single HTML string.
    """
    raise NotImplementedError()
