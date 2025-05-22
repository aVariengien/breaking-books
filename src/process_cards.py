#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
from typing_extensions import Annotated
from weasyprint import HTML

# Global constant for the template filename
CARD_TEMPLATE_FILENAME = "card_template_simple.html"

app = typer.Typer(help="CLI tool to generate PDF cards from a JSONL file and HTML template.")


def slugify(text: str) -> str:
    """Converts a string into a simplified, file-safe slug."""
    return "".join(filter(str.isalnum, text.lower().replace(" ", "_")))


def process_single_card(
    card_data: Dict[str, Any],
    card_index: int,
    template: Template,
    output_dir: Path,
    script_dir: Path,
) -> None:
    """Renders a single card from data to HTML and then to PDF."""
    card_title = card_data.get("title", f"Card_{card_index + 1}")
    base_filename = slugify(card_title) or f"card_{card_index + 1}"

    html_file_path = output_dir / f"{base_filename}.html"
    pdf_file_path = html_file_path.with_suffix(".pdf")

    rendered_html = template.render(card_data)
    html_file_path.write_text(rendered_html, encoding="utf-8")

    html_doc = HTML(string=rendered_html, base_url=str(script_dir))
    html_doc.write_pdf(pdf_file_path)


@app.command()
def generate_cards(
    jsonl_file_path: Annotated[
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
    template_file_name: Annotated[
        str, typer.Option(help="Name of the Jinja2 template file.")
    ] = CARD_TEMPLATE_FILENAME,
    output_directory_name: Annotated[
        Optional[str],
        typer.Option(help="Name for the output directory. If None, derived from input filename."),
    ] = None,
) -> None:
    """Processes a JSON Lines file to generate HTML cards and convert them to PDF."""

    effective_output_dir_name = output_directory_name or (
        jsonl_file_path.parent / (jsonl_file_path.stem + "_output")
    )
    output_dir = Path(effective_output_dir_name)
    output_dir.mkdir(exist_ok=True)

    script_dir = Path(__file__).resolve().parent

    # Assuming template is always in the same directory as the script
    file_loader = FileSystemLoader(str(script_dir))
    env = Environment(loader=file_loader, autoescape=select_autoescape(["html", "xml"]))

    # No try-except here: if template is missing, Jinja2 will raise TemplateNotFound
    # and the script will halt, as per the "ALWAYS there" assumption.
    template = env.get_template(template_file_name)

    print(f"Processing {jsonl_file_path}...")
    print(f"Template: {script_dir / template_file_name}")
    print(f"Processing {jsonl_file_path}...")
    print(f"Template: {script_dir / template_file_name}")
    print(f"Output will be saved in '{output_dir}'")

    with jsonl_file_path.open("r", encoding="utf-8") as f_in:
        for i, line in enumerate(f_in):
            line_content = line.strip()
            if not line_content:
                continue

            data = json.loads(line_content)
            process_single_card(data, i, template, output_dir, script_dir)
            print(f"Processed card {i + 1}: {data.get('title', 'Untitled')}")

    print("\nProcessing complete.")
    return output_dir


if __name__ == "__main__":
    app()
