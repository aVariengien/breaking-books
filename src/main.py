import os
from pathlib import Path

import typer

from pdf_combiner import combine
from process_cards import generate_cards

app = typer.Typer()


@app.command()
def main(
    input_file: Path = typer.Argument(..., help="Path to the input JSONL file."),
    show: bool = typer.Option(False, help="Show the output file in the default PDF viewer."),
) -> None:
    pdf_dir = generate_cards(input_file)
    output_file = input_file.with_name(f"{input_file.stem}_printable_cards.pdf").absolute()
    combine(pdf_dir, output_file)
    print(f"Printable cards saved to {output_file}")
    if show:
        cmd = f"firefox '{output_file}'"
        os.system(cmd)


if __name__ == "__main__":
    app()
