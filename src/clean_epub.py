import re
import subprocess
from pathlib import Path

import typer

app = typer.Typer()


LUA_FILTER_FILENAME = "remove_footnotes.lua"


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

    # Add unique IDs to HTML elements
    html_content = output_html.read_text(encoding="utf-8")
    modified_html = add_unique_ids(html_content)
    output_html.write_text(modified_html, encoding="utf-8")

    return output_html


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
