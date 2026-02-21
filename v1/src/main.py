import os
from pathlib import Path

import typer

from pdf_combiner import combine
from process_cards import generate_cards

app = typer.Typer()


@app.command()
def main(
    input_files: list[Path] = typer.Argument(..., help="Path to the input JSONL file."),
    four_up: bool = typer.Option(
        False,
        "--four-up",
        "-4",
        help="Use 4-up layout (4 A5 pages per A4 landscape sheet) instead of 2-up layout.",
    ),
    show: bool = typer.Option(False, help="Show the output file in the default PDF viewer."),
) -> None:
    for input_file in input_files:
        pdf_dir = generate_cards(input_file)

    output_file = input_file.with_name(f"{input_file.stem}_printable_cards.pdf")
    combine(pdf_dir, output_file, four_up)
    print(f"Printable cards saved to {output_file}")
    if show:
        cmd = f"firefox '{output_file}'"
        os.system(cmd)


if __name__ == "__main__":
    app()
