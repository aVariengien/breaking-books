"""CLI entry point for Breaking Books v2."""

import asyncio
import logging
import random
from datetime import datetime
from pathlib import Path

import typer
from slugify import slugify

from agent import run_agent
from lib import log
from lib.models import Config, OutDir, WorkDir
from tools.extract_book_content import load_book
from tools.merge_pdfs import merge_pdfs_to_print
from tools.render_template import cards_json_to_pdfs

app = typer.Typer(help="Transform a book into a printable flashcard deck.")
logger = logging.getLogger("bb.main")


@app.command()
def main(
    input_path: Path = typer.Argument(..., help="Path to the input file (EPUB, HTML, or Markdown)"),
    output_dir: Path | None = typer.Option(
        None,
        help="Directory for output files (default: output/{timestamp}_{random}_{input-slug})",
    ),
    num_cards: int = typer.Option(15, help="Target number of cards"),
    card_size: str = typer.Option("A6", help="Card size: A5 or A6"),
    model: str = typer.Option("haiku", help="Model: haiku, sonnet, or opus"),
    language: str | None = typer.Option(None, help="Output language (default: detect from book)"),
    max_qc_calls: int = typer.Option(3, help="Maximum quality control iterations"),
    user_preferences: str = typer.Option("", help="Free-text preferences forwarded to the agent"),
    resume: bool = typer.Option(False, help="Resume a previous agent session from output_dir"),
    instructions: str = typer.Option(
        "", help="Follow-up instructions when resuming (only used with --resume)"
    ),
) -> None:
    """
    Full pipeline:
    1. load_book(input_path)       →  book text  (EPUB, HTML, or Markdown)
    2. run_agent(…)                →  TMP/cards.json
    3. cards_json_to_pdfs(…)       →  TMP/renders/*.pdf (images generated on-demand)
    4. merge_pdfs_to_print(…)      →  output_dir/deck.pdf
    """
    if resume and output_dir is None:
        raise typer.BadParameter("--output-dir is required when using --resume")
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = random.randint(1000, 9999)
        slug = slugify(input_path.stem) or "output"
        output_dir = Path("output") / f"{timestamp}_{random_suffix}_{slug}"

    config = Config(
        num_cards=num_cards,
        card_size=card_size,  # type: ignore[arg-type]
        model=model,  # type: ignore[arg-type]
        language=language,
        max_qc_calls=max_qc_calls,
        user_preferences=user_preferences,
    )

    work_dir = WorkDir.create(output_dir / "tmp")
    out_dir = OutDir.create(output_dir / "out")
    log.setup(out_dir.log_path)

    # --- Step 1: load book (reuse cache on resume) ---
    if resume and out_dir.book_html_path.exists():
        logger.info("Loading cached book…")
        book_html = out_dir.book_html_path.read_text(encoding="utf-8")
    else:
        logger.info("Loading book from %s…", input_path)
        book_html = load_book(input_path)
        out_dir.book_html_path.write_text(book_html, encoding="utf-8")

    # --- Step 2: run agent ---
    asyncio.run(
        _run_agent(book_html, config, work_dir, out_dir, resume=resume, instructions=instructions)
    )

    # --- Step 3: render cards to individual PDFs ---
    logger.info("Rendering cards to PDF…")
    pdf_paths = cards_json_to_pdfs(
        work_dir.cards_json, work_dir.renders_dir, config, out_dir.images_dir
    )

    # --- Step 4: merge into a printable sheet ---
    logger.info("Merging PDFs…")
    merge_pdfs_to_print(pdf_paths, output_dir / "deck.pdf", card_size=config.card_size)

    typer.echo(f"Done! Output: {output_dir / 'deck.pdf'}")


async def _run_agent(
    book_html: str,
    config: Config,
    work_dir: WorkDir,
    out_dir: OutDir,
    *,
    resume: bool,
    instructions: str,
) -> None:
    async for message in run_agent(
        book_html, config, work_dir, out_dir, resume=resume, instructions=instructions
    ):
        log.log_message(message)


if __name__ == "__main__":
    app()
