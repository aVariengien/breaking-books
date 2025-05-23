from pathlib import Path
from typing import List, Optional, Tuple

import typer
from pypdf import PageObject, PdfReader, PdfWriter
from pypdf.errors import PdfReadError

# Standard page sizes in points (1 point = 1/72 inch)
# A4 Portrait: 210mm x 297mm
A4_PORTRAIT_WIDTH = 595.276
A4_PORTRAIT_HEIGHT = 841.890

# A4 Landscape: 297mm x 210mm
A4_LANDSCAPE_WIDTH = 841.890
A4_LANDSCAPE_HEIGHT = 595.276

# A5 Landscape: 210mm x 148mm (or 148.5mm for exact half of A4 width)
A5_LANDSCAPE_WIDTH = 595.276  # Standard A5 landscape width (210mm)
A5_LANDSCAPE_HEIGHT = 419.528  # Standard A5 landscape height (148mm)

# A6 Landscape: 148mm x 105mm
A6_LANDSCAPE_WIDTH = 419.528
A6_LANDSCAPE_HEIGHT = 297.638

# Tolerance for page size comparison
SIZE_TOLERANCE = 5.0  # points

app = typer.Typer(help="Combines PDFs into printable layouts.")


def get_pdf_files(input_dir: Path) -> List[Path]:
    """Get sorted list of PDF files from input directory."""
    pdf_files = sorted(list(input_dir.glob("*.pdf")))

    if not pdf_files:
        typer.secho(f"No PDF files found in {input_dir}.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"Found {len(pdf_files)} PDF files to process.")
    return pdf_files


def is_a4_page(page: PageObject) -> bool:
    """Check if a page is A4 size (either portrait or landscape)."""
    width, height = page.mediabox.width, page.mediabox.height

    # Check if it's A4 portrait
    if (
        abs(width - A4_PORTRAIT_WIDTH) < SIZE_TOLERANCE
        and abs(height - A4_PORTRAIT_HEIGHT) < SIZE_TOLERANCE
    ):
        return True

    # Check if it's A4 landscape
    if (
        abs(width - A4_LANDSCAPE_WIDTH) < SIZE_TOLERANCE
        and abs(height - A4_LANDSCAPE_HEIGHT) < SIZE_TOLERANCE
    ):
        return True

    return False


def is_a5_landscape_page(page: PageObject) -> bool:
    """Check if a page is A5 landscape size."""
    width, height = page.mediabox.width, page.mediabox.height

    return (
        abs(width - A5_LANDSCAPE_WIDTH) < SIZE_TOLERANCE
        and abs(height - A5_LANDSCAPE_HEIGHT) < SIZE_TOLERANCE
    )


def categorize_pdf(pdf_path: Path) -> Tuple[bool, List[PageObject]]:
    """
    Categorize a PDF as either A4 multi-page or A5 landscape single-page.

    Returns:
        Tuple[bool, List[PageObject]]: (is_a4, list of pages)
    """
    try:
        reader = PdfReader(str(pdf_path))
        if not reader.pages:
            typer.secho(f"Warning: {pdf_path.name} has no pages. Skipping.", fg=typer.colors.YELLOW)
            return False, []

        # Check the first page to determine the type
        first_page = reader.pages[0]

        # If it's a multi-page PDF with A4 pages, treat it as an A4 document
        if len(reader.pages) > 1 or is_a4_page(first_page):
            typer.echo(f"Detected A4 document: {pdf_path.name} ({len(reader.pages)} pages)")
            return True, list(reader.pages)

        # Otherwise, assume it's an A5 landscape single page
        typer.echo(f"Detected A5 landscape page: {pdf_path.name}")
        return False, [first_page]

    except PdfReadError:
        typer.secho(f"Error reading {pdf_path.name}. Skipping this file.", fg=typer.colors.RED)
        return False, []
    except Exception as e:
        typer.secho(
            f"An unexpected error occurred with {pdf_path.name}: {e}. Skipping this file.",
            fg=typer.colors.RED,
        )
        return False, []


def process_pdf_page(pdf_path: Path) -> Optional[PageObject]:
    """Process a single PDF file and return its first page if successful."""
    try:
        reader = PdfReader(str(pdf_path))
        if len(reader.pages) != 1:
            typer.secho(
                f"Warning: {pdf_path.name} has {len(reader.pages)} pages. Expected 1. Using the first page.",
                fg=typer.colors.YELLOW,
            )
        return reader.pages[0]
    except PdfReadError:
        typer.secho(f"Error reading {pdf_path.name}. Skipping this file.", fg=typer.colors.RED)
        return None
    except Exception as e:
        typer.secho(
            f"An unexpected error occurred with {pdf_path.name}: {e}. Skipping this file.",
            fg=typer.colors.RED,
        )
        return None


def create_2up_a4_page(writer: PdfWriter, pdf_paths: List[Path]) -> bool:
    """Create an A4 portrait page with up to two A5 landscape pages and add it to the writer.

    Args:
        writer: The PDF writer to add the page to
        pdf_paths: List of up to 2 PDF paths to add to the page

    Returns:
        bool: True if at least one page was successfully processed, False otherwise.
    """
    # Create a new blank A4 portrait page
    a4_page = writer.add_blank_page(width=A4_PORTRAIT_WIDTH, height=A4_PORTRAIT_HEIGHT)

    # Process the first PDF (top part of A4 page)
    if not pdf_paths:
        writer.pages.pop()
        return False

    a5_page1 = process_pdf_page(pdf_paths[0])
    if a5_page1 is None:
        # Remove the blank page we just added since we couldn't process the first PDF
        writer.pages.pop()
        return False

    # Place A5 page 1 on the top half
    offset_y_page1 = A4_PORTRAIT_HEIGHT - A5_LANDSCAPE_HEIGHT
    a4_page.merge_transformed_page(a5_page1, (1, 0, 0, 1, 0, offset_y_page1))
    typer.echo(f"Processed {pdf_paths[0].name} (top part)")

    # Process the second PDF (bottom part of A4 page) if available
    if len(pdf_paths) > 1:
        a5_page2 = process_pdf_page(pdf_paths[1])
        if a5_page2:
            # Place A5 page 2 on the bottom half
            a4_page.merge_transformed_page(a5_page2, (1, 0, 0, 1, 0, 0))
            typer.echo(f"Processed {pdf_paths[1].name} (bottom part)")

    return True


def create_4up_a4_page(writer: PdfWriter, pdf_paths: List[Path]) -> bool:
    """Create an A4 landscape page with up to four A5 pages (scaled to A6) and add it to the writer.

    Args:
        writer: The PDF writer to add the page to
        pdf_paths: List of up to 4 PDF paths to add to the page

    Returns:
        bool: True if at least one page was successfully processed, False otherwise.
    """
    # Create a new blank A4 landscape page
    a4_page = writer.add_blank_page(width=A4_LANDSCAPE_WIDTH, height=A4_LANDSCAPE_HEIGHT)

    # Check if we have any PDFs to process
    if not pdf_paths:
        writer.pages.pop()
        return False

    # Scale factor for A5 to A6 - increased from 0.5 to 0.65 for better readability
    scale = 0.65

    # Calculate margins and spacing
    horizontal_spacing = 10  # Space between columns
    vertical_spacing = 10  # Space between rows

    # Calculate effective width and height after scaling
    effective_width = A5_LANDSCAPE_WIDTH * scale
    effective_height = A5_LANDSCAPE_HEIGHT * scale

    # Calculate positions with margins to center the content
    horizontal_margin = (A4_LANDSCAPE_WIDTH - (2 * effective_width) - horizontal_spacing) / 2
    vertical_margin = (A4_LANDSCAPE_HEIGHT - (2 * effective_height) - vertical_spacing) / 2

    # Process up to 4 PDFs
    positions = [
        # Top-left
        (horizontal_margin, A4_LANDSCAPE_HEIGHT - effective_height - vertical_margin),
        # Top-right
        (
            horizontal_margin + effective_width + horizontal_spacing,
            A4_LANDSCAPE_HEIGHT - effective_height - vertical_margin,
        ),
        # Bottom-left
        (horizontal_margin, vertical_margin),
        # Bottom-right
        (horizontal_margin + effective_width + horizontal_spacing, vertical_margin),
    ]

    success = False

    for i, pdf_path in enumerate(pdf_paths[:4]):  # Limit to 4 PDFs
        a5_page = process_pdf_page(pdf_path)
        if a5_page is None:
            continue

        # Get position for this page
        pos_x, pos_y = positions[i]

        # Transform matrix: (scale_x, skew_x, skew_y, scale_y, translate_x, translate_y)
        transform = (scale, 0, 0, scale, pos_x, pos_y)

        # Place the scaled page at the correct position
        a4_page.merge_transformed_page(a5_page, transform)
        typer.echo(f"Processed {pdf_path.name} (position {i+1})")
        success = True

    # If no pages were successfully processed, remove the blank page
    if not success:
        writer.pages.pop()
        return False

    return True


def add_a4_pages(writer: PdfWriter, pages: List[PageObject], scale: float = 1.0) -> None:
    """Add A4 pages directly to the writer, optionally scaling them.

    Args:
        writer: The PDF writer to add the page to
        pages: List of A4 pages to add
        scale: Scale factor (1.0 for no scaling, 0.5 for half size)
    """
    for page in pages:
        if scale != 1.0:
            # Create a blank page with scaled dimensions
            width, height = page.mediabox.width * scale, page.mediabox.height * scale
            new_page = writer.add_blank_page(width=width, height=height)

            # Apply scaling transformation centered on the page
            transform = (scale, 0, 0, scale, 0, 0)

            new_page.merge_transformed_page(page, transform)
        else:
            # Add page directly if no scaling is needed
            writer.add_page(page)


def write_output_pdf(writer: PdfWriter, output_file: Path) -> None:
    """Write the PDF to the output file."""
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


@app.command()
def combine(
    input_dir: Path = typer.Option(
        ...,
        "--input-dir",
        "-i",
        help="Directory containing PDF files to combine.",
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
        help="Path for the combined PDF file.",
        writable=True,  # Checks if parent dir is writable for new file
        dir_okay=False,
        resolve_path=True,
    ),
    four_up: bool = typer.Option(
        False,
        "--four-up",
        "-4",
        help="Use 4-up layout for A5 pages (4 A5 pages per A4 landscape sheet) instead of 2-up layout.",
    ),
    scale_a4: bool = typer.Option(
        False,
        "--scale-a4",
        "-s",
        help="Scale A4 pages to A5 size (50% reduction) for more efficient printing.",
    ),
):
    """
    Combines PDFs from an input directory into a single printable PDF.

    Handles two types of input PDFs:
    1. Single-page A5 landscape PDFs - These are combined into A4 sheets (2-up or 4-up)
    2. Multi-page A4 PDFs - These are appended as-is, or scaled to A5 if --scale-a4 is used

    Layout options for A5 pages:
    - Default (--four-up=False): Each A4 portrait page will contain two A5 pages, one above the other.
    - 4-up (--four-up=True): Each A4 landscape page will contain four A5 pages (scaled to A6), arranged in a 2x2 grid.

    A4 pages can be scaled down to A5 size using the --scale-a4 option.
    """
    typer.secho(f"Input directory: {input_dir}", fg=typer.colors.BLUE)
    typer.secho(f"Output file: {output_file}", fg=typer.colors.BLUE)
    typer.secho(f"Layout for A5 pages: {'4-up' if four_up else '2-up'}", fg=typer.colors.BLUE)
    typer.secho(f"Scale A4 pages to A5: {'Yes' if scale_a4 else 'No'}", fg=typer.colors.BLUE)

    # Get PDF files from input directory
    pdf_files = get_pdf_files(input_dir)

    # Create PDF writer
    writer = PdfWriter()

    # Categorize PDFs into A4 and A5
    a5_pdf_paths = []
    a4_pages = []

    for pdf_path in pdf_files:
        is_a4, pages = categorize_pdf(pdf_path)
        if is_a4:
            a4_pages.extend(pages)
        else:
            if pages:  # Only add if we got valid pages
                a5_pdf_paths.append(pdf_path)

    # Process A5 landscape PDFs
    if a5_pdf_paths:
        typer.secho(f"Processing {len(a5_pdf_paths)} A5 landscape PDFs...", fg=typer.colors.GREEN)

        if not four_up:
            # Process PDF files in pairs
            for i in range(0, len(a5_pdf_paths), 2):
                pdf_paths = a5_pdf_paths[i : i + 2]
                create_2up_a4_page(writer, pdf_paths)
        else:
            # Process PDF files in groups of 4
            for i in range(0, len(a5_pdf_paths), 4):
                pdf_paths = a5_pdf_paths[i : i + 4]
                create_4up_a4_page(writer, pdf_paths)

    # Process A4 PDFs
    if a4_pages:
        typer.secho(f"Processing {len(a4_pages)} A4 pages...", fg=typer.colors.GREEN)
        scale = 0.5 if scale_a4 else 1.0
        add_a4_pages(writer, a4_pages, scale)

    # Write output PDF
    write_output_pdf(writer, output_file)


if __name__ == "__main__":
    app()
