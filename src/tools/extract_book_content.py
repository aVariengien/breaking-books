"""Convert various book formats into clean HTML for LLM consumption."""

import re
import subprocess
import tempfile
from pathlib import Path


_LUA_FILTER = Path(__file__).parent / "remove_footnotes.lua"

_SUPPORTED_SUFFIXES = {".epub", ".html", ".htm", ".md", ".markdown", ".txt"}


def load_book(path: Path) -> str:
    """
    Load a book from any supported format and return clean HTML.

    - .epub            → pandoc EPUB conversion + clean_html
    - .html / .htm     → clean_html directly
    - .md / .markdown  → pandoc markdown→HTML + clean_html
    """
    suffix = path.suffix.lower()
    if suffix == ".epub":
        return extract_book_content(path)
    elif suffix in (".html", ".htm"):
        return clean_html(path.read_text(encoding="utf-8"))
    elif suffix in (".md", ".markdown", ".txt"):
        return path.read_text(encoding="utf-8")
    else:
        raise ValueError(
            f"Unsupported file format: {suffix!r}. "
            f"Supported: {', '.join(sorted(_SUPPORTED_SUFFIXES))}"
        )


def extract_book_content(epub_path: Path) -> str:
    """
    Convert an EPUB file to clean, normalized HTML.

    - Strips footnotes, headers, and page numbers.
    - Normalizes image paths.

    Returns the full book as a single HTML string.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        output_html = tmp_path / "book.html"
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        subprocess.run(
            [
                "pandoc",
                str(epub_path),
                "-o",
                str(output_html),
                "--standalone",
                "--extract-media",
                str(media_dir),
                f"--lua-filter={_LUA_FILTER}",
            ],
            check=True,
            text=True,
        )

        html = output_html.read_text(encoding="utf-8")

    return clean_html(html)


def clean_html(html: str) -> str:
    html = _normalize_image_paths(html)
    html = _normalize_img_tag_whitespace(html)
    html = _remove_noisy_attributes(html)
    html = _remove_style_tags(html)
    # Three times for nested tags
    html = _remove_empty_tags(html)
    html = _remove_empty_tags(html)
    html = _remove_empty_tags(html)
    return html


def _normalize_image_paths(html: str) -> str:
    pattern = r'src="([^"]*[/\\])?([^"]*\.(png|jpg|jpeg|gif|svg|webp))"'
    return re.sub(pattern, r'src="\2"', html, flags=re.IGNORECASE)


def _normalize_img_tag_whitespace(html: str) -> str:
    pattern = r"<img\s+([^>]*?)>"

    def replace_img_tag(match):
        attrs = re.sub(r"\s+", " ", match.group(1).strip())
        return f"<img {attrs}>"

    return re.sub(pattern, replace_img_tag, html, flags=re.DOTALL)


def _remove_empty_tags(html: str) -> str:
    return re.sub(r"<[^>]*>\s*</[^>]*>", "", html, flags=re.IGNORECASE)


def _remove_noisy_attributes(html: str) -> str:
    return re.sub(r'[\s\n]+(href|id|class)="[^"]*"', "", html, flags=re.IGNORECASE)


def _remove_style_tags(html: str) -> str:
    return re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.IGNORECASE | re.DOTALL)


if __name__ == "__main__":
    # Quick quality check: run on an EPUB from data/ and print the extracted HTML.
    # Usage: python -m tools.extract_book_content [path/to/book.epub]
    import random
    import sys
    from pathlib import Path

    data_dir = Path(__file__).parents[2] / "data"
    if len(sys.argv) > 1:
        epub = Path(sys.argv[1])
    else:
        epubs = sorted(data_dir.glob("*.epub"))
        if not epubs:
            sys.exit(f"No EPUB files found in {data_dir}")
        epub = random.choice(epubs)
        print(f"Picked: {epub.name}", file=sys.stderr)

    print(extract_book_content(epub))
