import subprocess
from pathlib import Path

import typer

app = typer.Typer()

LUA_FILTER_FILENAME = "remove_footnotes.lua"


@app.command()
def process_epub(
    input_epub: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the input EPUB file.",
    ),
    output_html: Path = typer.Argument(
        None,
        file_okay=True,
        dir_okay=False,
        writable=True,
        help="Path for the output HTML file. Defaults to the input filename with an .html extension.",
    ),
    extract_media_dir: Path = typer.Option(
        None,
        help="Directory to extract media files to. Defaults to input filename with _media suffix. It will be created if it doesn't exist.",
    ),
):
    """
    Converts an EPUB file to a clean HTML file, removing footnotes
    and extracting media.
    """
    script_dir = Path(__file__).parent.resolve()
    lua_filter_path = script_dir / LUA_FILTER_FILENAME

    # Determine output_html if not provided
    if output_html is None:
        output_html = input_epub.with_suffix(".html")

    # Determine extract_media_dir if not provided
    if extract_media_dir is None:
        extract_media_dir = input_epub.parent / f"{input_epub.stem}_media"

    # Ensure extract_media_dir exists and inform user
    extract_media_dir.mkdir(parents=True, exist_ok=True)
    typer.echo(
        f"Info: Media will be extracted to '{extract_media_dir}'. This directory will be created if it doesn't exist. Existing files may be overwritten."
    )

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

    typer.echo(f"Running command: {' '.join(pandoc_command)}")

    subprocess.run(pandoc_command, check=True, text=True)
    typer.echo(
        f"Successfully converted '{input_epub}' to '{output_html}' with media extracted to '{extract_media_dir}'"
    )


if __name__ == "__main__":
    app()
