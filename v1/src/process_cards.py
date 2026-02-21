#!/usr/bin/env python3
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import markdown
import typer
from jinja2 import Environment, FileSystemLoader, select_autoescape
from joblib import Parallel, delayed
from typing_extensions import Annotated
from weasyprint import HTML

from constants import (
    CARD_TEMPLATE_FILENAME,
    SECTION_TEMPLATE_FILENAME,
    TEMPLATE_DIR,
    TOC_TEMPLATE_FILENAME,
)

# Common type annotations
JsonLinesInputFile = Annotated[
    Path,
    typer.Argument(
        help="Path to the input JSON Lines file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
    ),
]

JsonInputFile = Annotated[
    Path,
    typer.Argument(
        help="Path to the input JSON file with book structure.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
    ),
]

NJobsOption = Annotated[
    Optional[int],
    typer.Option(help="Number of parallel jobs. If None, uses number of CPU cores."),
]

app = typer.Typer(help="CLI tool to generate PDF cards from a JSONL file and HTML template.")


def slugify(text: str) -> str:
    """Converts a string into a simplified, file-safe slug."""
    return "".join(filter(str.isalnum, text.lower().replace(" ", "_")))


def create_pdf(
    template_data: Dict[str, Any],
    template_file_name: str,
    output_dir: Path,
    title: str | None = None,
) -> Path:
    """Renders a single card from data to HTML and then to PDF."""
    # Create a new template environment for each worker
    file_loader = FileSystemLoader(TEMPLATE_DIR)
    env = Environment(loader=file_loader, autoescape=select_autoescape(["html", "xml"]))
    template = env.get_template(template_file_name)

    if title is None:
        card_title = template_data.get("title", template_data.get("section_name", "toc"))
    else:
        card_title = title
    base_filename = slugify(card_title)

    html_file_path = output_dir / f"{base_filename}.html"
    pdf_file_path = html_file_path.with_suffix(".pdf")

    # Edit description to convert markdown to html
    fields_to_markdown = ["description", "section_introduction"]
    for field in fields_to_markdown:
        if field in template_data:
            template_data[field] = markdown.markdown(template_data[field])

    rendered_html = template.render(template_data)
    html_file_path.write_text(rendered_html, encoding="utf-8")

    html_doc = HTML(string=rendered_html)
    html_doc.write_pdf(pdf_file_path)

    return pdf_file_path


def _process_cards_parallel(
    cards_data: list[Dict[str, Any]],
    template_filename: str,
    output_dir: Path,
    n_jobs: int | None = None,
) -> list[Path]:
    """Common function to process cards in parallel."""
    output_dir.mkdir(exist_ok=True)

    # Use all CPU cores if n_jobs is not specified
    if n_jobs is None:
        n_jobs = os.cpu_count()

    # Process cards in parallel
    results = Parallel(n_jobs=n_jobs, return_as="generator_unordered")(
        delayed(create_pdf)(data, template_filename, output_dir) for data in cards_data
    )

    # Process results as they complete
    completed = 0
    pdf_paths = []
    for file_path in results:
        completed += 1
        print(f"Processed card {completed}/{len(cards_data)}: {file_path}")
        pdf_paths.append(file_path)

    return pdf_paths


@app.command()
def generate_cards(input_file: JsonLinesInputFile, n_jobs: NJobsOption = None) -> list[Path]:
    """Processes a JSON Lines file to generate HTML cards and convert them to PDF."""
    output_dir = input_file.parent / (input_file.stem + "_output")

    cards_data = []
    with input_file.open("r", encoding="utf-8") as f_in:
        for i, line in enumerate(f_in):
            line_content = line.strip()
            if not line_content:
                continue
            cards_data.append(json.loads(line_content))

    return _process_cards_parallel(cards_data, CARD_TEMPLATE_FILENAME, output_dir, n_jobs)


@app.command()
def generate_section_cards(input_file: JsonInputFile, n_jobs: NJobsOption = None) -> list[Path]:
    """Processes a JSON file with book structure to generate section cards and TOC as PDFs."""
    output_dir = input_file.parent / (input_file.stem + "_output")
    output_dir.mkdir(exist_ok=True)

    book_structure = json.loads(input_file.read_text(encoding="utf-8"))
    cards_data = book_structure["sections"]

    return _process_cards_parallel(cards_data, SECTION_TEMPLATE_FILENAME, output_dir, n_jobs)


@app.command()
def generate_toc(json_structure: JsonInputFile) -> Path:
    """Generate only the table of contents PDF from a JSON structure file."""
    output_dir = json_structure.parent / (json_structure.stem + "_output")
    output_dir.mkdir(exist_ok=True)

    book_structure = json.loads(json_structure.read_text(encoding="utf-8"))
    return create_pdf(book_structure, TOC_TEMPLATE_FILENAME, output_dir, title="toc")


if __name__ == "__main__":
    app()
