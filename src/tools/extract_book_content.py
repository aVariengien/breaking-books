"""Convert an EPUB (or other input format) into clean HTML for LLM consumption."""

import re
import subprocess
import tempfile
from pathlib import Path


_LUA_FILTER = Path(__file__).parent / "remove_footnotes.lua"


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

    return _clean_html(html)


def _clean_html(html: str) -> str:
    html = _normalize_image_paths(html)
    html = _normalize_img_tag_whitespace(html)
    html = _remove_empty_spans(html)
    html = _remove_href_and_id_attributes(html)
    html = _remove_style_tags(html)
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


def _remove_empty_spans(html: str) -> str:
    return re.sub(r"<span[^>]*>\s*</span>", "", html, flags=re.IGNORECASE)


def _remove_href_and_id_attributes(html: str) -> str:
    return re.sub(r'[\s\n]+(href|id)="[^"]*"', "", html, flags=re.IGNORECASE)


def _remove_style_tags(html: str) -> str:
    return re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.IGNORECASE | re.DOTALL)
