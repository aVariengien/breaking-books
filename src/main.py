"""CLI entry point for Breaking Books v2."""

from pathlib import Path

import typer


app = typer.Typer(help="Transform a book into a printable flashcard deck.")


@app.command()
def main(
    epub_path: Path = typer.Argument(..., help="Path to the input EPUB file"),
    output_dir: Path = typer.Option(Path("output"), help="Directory for output files"),
    num_cards: int = typer.Option(40, help="Target number of cards"),
    card_size: str = typer.Option("A6", help="Card size: A5 or A6"),
    language: str | None = typer.Option(None, help="Output language (default: detect from book)"),
    max_qc_calls: int = typer.Option(3, help="Maximum quality control iterations"),
    user_preferences: str = typer.Option("", help="Free-text preferences forwarded to the agent"),
    resume: bool = typer.Option(False, help="Resume a previous agent session from output_dir"),
) -> None:
    """
    Full pipeline:
    1. extract_book_content(epub_path)
    2. build_agent_prompt(book_html, config)
    3. run_agent(…) → populates work_dir/cards.json
    4. cards_json_to_pdfs(…)
    5. merge_pdfs_to_print(…)
    """
    raise NotImplementedError()


if __name__ == "__main__":
    app()
