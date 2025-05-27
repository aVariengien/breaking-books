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

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
CARD_TEMPLATE_FILENAME = "card_template.html"
SECTION_TEMPLATE_FILENAME = "section_card_template.html"
TOC_TEMPLATE_FILENAME = "toc_template.html"
KEY_PASSAGES_TEMPLATE_FILENAME = "key_passages_template.html"


app = typer.Typer(help="CLI tool to generate PDF cards from a JSONL file and HTML template.")


def slugify(text: str) -> str:
    """Converts a string into a simplified, file-safe slug."""
    return "".join(filter(str.isalnum, text.lower().replace(" ", "_")))


def create_pdf(
    template_data: Dict[str, Any],
    template_file_name: str,
    output_dir: Path,
    title: str | None = None,
) -> None:
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

    return card_title


@app.command()
def generate_cards(
    input_file: Annotated[
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
    ],
    n_jobs: Annotated[
        Optional[int],
        typer.Option(help="Number of parallel jobs. If None, uses number of CPU cores."),
    ] = None,
) -> None:
    """Processes a JSON Lines file to generate HTML cards and convert them to PDF."""

    output_dir = input_file.parent / (input_file.stem + "_output")
    output_dir.mkdir(exist_ok=True)

    # Use all CPU cores if n_jobs is not specified
    if n_jobs is None:
        n_jobs = os.cpu_count()

    # Load all card data first
    if input_file.suffix == ".jsonl":
        template = CARD_TEMPLATE_FILENAME
        cards_data = []
        with input_file.open("r", encoding="utf-8") as f_in:
            for i, line in enumerate(f_in):
                line_content = line.strip()
                if not line_content:
                    continue
                cards_data.append(json.loads(line_content))
    else:  # It's sections
        template = SECTION_TEMPLATE_FILENAME
        book_structure = json.loads(input_file.read_text(encoding="utf-8"))
        cards_data = book_structure["sections"]

        # Create TOC
        create_pdf(book_structure, TOC_TEMPLATE_FILENAME, output_dir, title="toc")

        # Create pdf extracts
        # extract_data = []
        # for section in book_structure["sections"]:
        #     extract_data.extend(section["key_passages"][:1])

        # results = Parallel(n_jobs=n_jobs, return_as="generator_unordered")(
        #     delayed(create_pdf)(data, KEY_PASSAGES_TEMPLATE_FILENAME, output_dir, title=f"passage_{i}") for i, data in enumerate(extract_data)
        # )
        # completed = 0
        # for title in results:
        #     completed += 1
        #     print(f"Processed extract {completed}/{len(extract_data)}")

    # Process cards in paralle
    results = Parallel(n_jobs=n_jobs, return_as="generator_unordered")(
        delayed(create_pdf)(data, template, output_dir) for data in cards_data
    )

    # Process results as they complete
    completed = 0
    for title in results:
        completed += 1
        print(f"Processed card {completed}/{len(cards_data)}: {title}")

    return output_dir


if __name__ == "__main__":
    app()
