import re
import subprocess
from pathlib import Path

import typer

app = typer.Typer()


LUA_FILTER_FILENAME = "remove_footnotes.lua"


def normalize_image_paths(html_content: str) -> str:
    """
    Normalize image paths to be deterministic (just filenames, no directory paths).

    Pandoc generates absolute paths based on where files are processed, causing the same
    EPUB to produce different HTML when processed from different locations. This function
    strips all directory paths, keeping only filenames for deterministic output.
    """

    def replace_img_src(match):
        # Extract just the filename from the path
        full_path = match.group(1)
        filename = Path(full_path).name
        return f'src="{filename}"'

    # Replace src="any/path/to/image.ext" with src="image.ext"
    # Handles both forward and backslashes for cross-platform compatibility
    pattern = r'src="([^"]*[/\\])?([^"]*\.(png|jpg|jpeg|gif|svg|webp))"'
    return re.sub(pattern, r'src="\2"', html_content, flags=re.IGNORECASE)


def normalize_img_tag_whitespace(html_content: str) -> str:
    """
    Normalize whitespace around img tags to ensure deterministic formatting.

    Pandoc can produce different whitespace/line breaks around <img> tags depending
    on input file paths length. This causes the same EPUB to generate
    different HTML formatting, breaking determinism used for caching. We normalize all whitespace
    within img tags to single spaces.
    """
    # Pattern to match img tags with any amount of whitespace/newlines
    pattern = r"<img\s+([^>]*?)>"

    def replace_img_tag(match):
        # Get all attributes and normalize whitespace between them
        attrs = match.group(1)
        # Replace any sequence of whitespace (including newlines) with single spaces
        attrs = re.sub(r"\s+", " ", attrs.strip())
        return f"<img {attrs}>"

    return re.sub(pattern, replace_img_tag, html_content, flags=re.DOTALL)


def remove_empty_spans(html_content: str) -> str:
    """
    Remove empty span tags that contain no text content.

    These are often anchor links or references from EPUB that clutter the HTML.
    Handles spans with any attributes (including multiple id attributes).
    """
    # Match span tags that contain only whitespace (or nothing) between opening and closing tags
    # This handles spans with any attributes, including malformed ones with duplicate ids
    pattern = r"<span[^>]*>\s*</span>"
    return re.sub(pattern, "", html_content, flags=re.IGNORECASE)


def remove_href_and_id_attributes(html_content: str) -> str:
    """
    Remove href and id attributes from all elements.
    """
    # [\s\n]+ -> one or more whitespace or newlines before
    pattern = r'[\s\n]+(href|id)="[^"]*"'
    return re.sub(pattern, "", html_content, flags=re.IGNORECASE)


def add_unique_ids(html_content: str) -> str:
    """Add unique IDs to all HTML elements."""
    id_counter = 0

    def replace_tag(match):
        nonlocal id_counter
        id_counter += 1
        # If there's whitespace after the tag name, keep it, otherwise add a space
        end = match.group(2) or " "
        return f'{match.group(1)} id="tag-{id_counter}"{end}'

    # Match any opening HTML tag, with or without attributes
    pattern = r"(<\w+)([\s>])"
    return re.sub(pattern, replace_tag, html_content)


def convert_epub_to_html(
    input_epub: Path,
    output_html: Path | None = None,
    extract_media_dir: Path | None = None,
) -> Path:
    """
    Convert an EPUB file to clean HTML, removing footnotes, adding unique IDs to all HTML elements, and extracting media.

    Args:
        input_epub: Path to the input EPUB file
        output_html: Path for output HTML file. Defaults to input filename with .html extension
        extract_media_dir: Directory to extract media files to. Defaults to input filename with _media suffix

    Returns:
        Path to the generated HTML file
    """
    script_dir = Path(__file__).parent.resolve()
    lua_filter_path = script_dir / LUA_FILTER_FILENAME

    # Set defaults if not provided
    if output_html is None:
        output_html = input_epub.with_suffix(".html")

    if extract_media_dir is None:
        extract_media_dir = input_epub.parent / f"{input_epub.stem}_media"

    # Ensure extract_media_dir exists
    extract_media_dir.mkdir(parents=True, exist_ok=True)

    # Run pandoc conversion
    pandoc_command = [
        "pandoc",
        str(input_epub),
        "-o",
        str(output_html),
        "--standalone",
        "--extract-media",
        str(extract_media_dir),
        f"--lua-filter={lua_filter_path}",
    ]

    subprocess.run(pandoc_command, check=True, text=True)

    # Post-process the HTML to ensure deterministic output
    html_content = output_html.read_text(encoding="utf-8")
    html_content = convert_html_to_clean_html(html_content)
    output_html.write_text(html_content, encoding="utf-8")

    return output_html


def convert_html_to_clean_html(html: str) -> str:
    """
    Clean an HTML file, removing footnotes, id/hrefs, adding unique IDs to all HTML elements.
    """

    # Step 1: Fix directory-dependent image paths from pandoc
    # Pandoc generates different absolute paths based on processing location
    html = normalize_image_paths(html)

    # Step 2: Remove extra whitespace from pandoc, that comes when longer file
    # names are used (it splits lines differently)
    html = normalize_img_tag_whitespace(html)

    # Step 3: Remove empty spans, href and id attributes -> less tokens
    html = remove_empty_spans(html)
    html = remove_href_and_id_attributes(html)

    # Step 4: Add unique IDs to be able to reference specific elements
    html = add_unique_ids(html)

    return html


@app.command()
def epub_to_clean_html(
    input_epub: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the input EPUB file.",
    ),
    extract_media_dir: Path = typer.Option(
        None,
        help="Directory to extract media files to. Defaults to input filename with _media suffix. It will be created if it doesn't exist.",
    ),
):

    result_path = convert_epub_to_html(input_epub, extract_media_dir=extract_media_dir)

    typer.echo(
        f"Successfully converted '{input_epub}' to '{result_path}' with media extracted to '{extract_media_dir}'"
    )


if __name__ == "__main__":
    app()
