from pathlib import Path

import typer
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

# Standard page sizes in points (1 point = 1/72 inch)
# A4 Portrait: 210mm x 297mm
A4_PORTRAIT_WIDTH = 595.276
A4_PORTRAIT_HEIGHT = 841.890

# A5 Landscape: 210mm x 148mm (or 148.5mm for exact half of A4 width)
# Using 148mm as standard A5 height.
A5_LANDSCAPE_WIDTH = 595.276  # Standard A5 landscape width (210mm)
A5_LANDSCAPE_HEIGHT = 419.528  # Standard A5 landscape height (148mm)

app = typer.Typer(help="Combines A5 landscape PDFs into an A4 portrait PDF.")


@app.command()
def combine(
    input_dir: Path = typer.Option(
        ...,
        "--input-dir",
        "-i",
        help="Directory containing A5 landscape, single-page PDF files.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
    ),
    output_file: Path = typer.Option(
        ...,
        "--output-file",
        "-o",
        help="Path for the combined A4 PDF file.",
        writable=True,  # Checks if parent dir is writable for new file
        dir_okay=False,
        resolve_path=True,
    ),
):
    """
    Combines single-page A5 landscape PDFs from an input directory
    into a single A4 portrait PDF.
    Each A4 page will contain two A5 pages, one above the other.
    """
    typer.secho(f"Input directory: {input_dir}", fg=typer.colors.BLUE)
    typer.secho(f"Output file: {output_file}", fg=typer.colors.BLUE)

    pdf_files = sorted(list(input_dir.glob("*.pdf")))

    if not pdf_files:
        typer.secho(f"No PDF files found in {input_dir}.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"Found {len(pdf_files)} PDF files to process.")

    writer = PdfWriter()

    for i in range(0, len(pdf_files), 2):
        pdf_path1 = pdf_files[i]
        pdf_path2 = pdf_files[i + 1] if (i + 1) < len(pdf_files) else None

        # Create a new blank A4 portrait page.
        # The PageObject is automatically added to the writer instance.
        a4_page = writer.add_blank_page(width=A4_PORTRAIT_WIDTH, height=A4_PORTRAIT_HEIGHT)

        # Process the first PDF (top part of A4 page)
        try:
            reader1 = PdfReader(str(pdf_path1))
            if len(reader1.pages) != 1:
                typer.secho(
                    f"Warning: {pdf_path1.name} has {len(reader1.pages)} pages. Expected 1. Using the first page.",
                    fg=typer.colors.YELLOW,
                )
            a5_page1 = reader1.pages[0]

            # Verify A5 landscape dimensions (optional, as per prompt "assume it's the case")
            # media_box1 = a5_page1.mediabox
            # if not (abs(media_box1.width - A5_LANDSCAPE_WIDTH) < 2 and abs(media_box1.height - A5_LANDSCAPE_HEIGHT) < 2):
            #     typer.secho(f"Warning: {pdf_path1.name} (page 1) may not be A5 landscape. Dimensions: {media_box1.width:.2f}x{media_box1.height:.2f} pt.", fg=typer.colors.YELLOW)

            # Place A5 page 1 on the top half.
            # The transformation is (scale_x, skew_x, skew_y, scale_y, translate_x, translate_y).
            # Origin (0,0) for the A5 page will be moved to (0, A4_PORTRAIT_HEIGHT - A5_LANDSCAPE_HEIGHT).
            offset_y_page1 = A4_PORTRAIT_HEIGHT - A5_LANDSCAPE_HEIGHT
            a4_page.merge_transformed_page(a5_page1, (1, 0, 0, 1, 0, offset_y_page1))
            typer.echo(f"Processed {pdf_path1.name} (top part)")

        except PdfReadError:
            typer.secho(f"Error reading {pdf_path1.name}. Skipping this file.", fg=typer.colors.RED)
            continue  # Skip to next pair if first PDF is unreadable

        except Exception as e:
            typer.secho(
                f"An unexpected error occurred with {pdf_path1.name}: {e}. Skipping this file.",
                fg=typer.colors.RED,
            )
            continue

        if pdf_path2:
            try:
                reader2 = PdfReader(str(pdf_path2))
                if len(reader2.pages) != 1:
                    typer.secho(
                        f"Warning: {pdf_path2.name} has {len(reader2.pages)} pages. Expected 1. Using the first page.",
                        fg=typer.colors.YELLOW,
                    )
                a5_page2 = reader2.pages[0]

                # media_box2 = a5_page2.mediabox
                # if not (abs(media_box2.width - A5_LANDSCAPE_WIDTH) < 2 and abs(media_box2.height - A5_LANDSCAPE_HEIGHT) < 2):
                #     typer.secho(f"Warning: {pdf_path2.name} (page 1) may not be A5 landscape. Dimensions: {media_box2.width:.2f}x{media_box2.height:.2f} pt.", fg=typer.colors.YELLOW)

                # Place A5 page 2 on the bottom half (no y-translation needed for its content).
                a4_page.merge_transformed_page(a5_page2, (1, 0, 0, 1, 0, 0))
                typer.echo(f"Processed {pdf_path2.name} (bottom part)")

            except PdfReadError:
                typer.secho(
                    f"Error reading {pdf_path2.name}. It will be omitted from the current A4 page.",
                    fg=typer.colors.RED,
                )
            except Exception as e:
                typer.secho(
                    f"An unexpected error occurred with {pdf_path2.name}: {e}. It will be omitted.",
                    fg=typer.colors.RED,
                )

    if not writer.pages:
        typer.secho(
            "No pages were processed successfully. Output PDF will not be created.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    try:
        with open(output_file, "wb") as fp:
            writer.write(fp)
        typer.secho(f"Successfully combined PDFs into {output_file}", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Error writing output file {output_file}: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
