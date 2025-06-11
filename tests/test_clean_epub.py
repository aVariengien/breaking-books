import difflib
import shutil
import tempfile
from pathlib import Path

import pytest

from src.clean_epub import convert_epub_to_html, normalize_image_paths


@pytest.fixture
def test_epub() -> Path:
    """Fixture providing the path to the test EPUB file"""
    epub_path = Path(__file__).parent / "fixtures" / "book.epub"
    assert epub_path.exists(), f"Test EPUB file not found at {epub_path}"
    return epub_path


def test_convert_epub_to_html_deterministic(test_epub: Path):
    """Test that the same EPUB produces identical HTML content regardless of processing location."""

    # Create two temporary directories and copy the EPUB with different filenames
    with tempfile.TemporaryDirectory() as temp_dir1, tempfile.TemporaryDirectory() as temp_dir2:
        temp_path1 = Path(temp_dir1)
        temp_path2 = Path(temp_dir2)

        # Copy the EPUB to different locations with different filenames
        epub_copy1 = temp_path1 / "book.epub"
        epub_copy2 = temp_path2 / "different_name.epub"

        shutil.copy2(test_epub, epub_copy1)
        shutil.copy2(test_epub, epub_copy2)

        # Process both EPUBs
        html_output1 = convert_epub_to_html(epub_copy1)
        html_output2 = convert_epub_to_html(epub_copy2)

        # Read the HTML content
        html_content1 = html_output1.read_text(encoding="utf-8")
        html_content2 = html_output2.read_text(encoding="utf-8")

        # Compare HTML content - should be identical
        if html_content1 != html_content2:
            # Generate a helpful diff to show where they differ
            diff = list(
                difflib.unified_diff(
                    html_content1.splitlines(keepends=True),
                    html_content2.splitlines(keepends=True),
                    fromfile=f"html_from_{epub_copy1.name}",
                    tofile=f"html_from_{epub_copy2.name}",
                    n=3,  # Show 3 lines of context
                )
            )
            diff_text = "".join(diff[:50])  # Limit diff output to first 50 lines
            if len(diff) > 50:
                diff_text += "\n... (diff truncated, showing first 50 lines)\n"

            pytest.fail(f"HTML content differs between processing locations:\n{diff_text}")


def test_normalize_image_paths():
    """Test the normalize_image_paths function directly."""

    # Test various image path formats
    test_cases = [
        # (input_html, expected_output)
        (
            '<img src="images/chapter1/figure1.png" alt="test">',
            '<img src="figure1.png" alt="test">',
        ),
        ('<img src="./media/subfolder/image.jpg">', '<img src="image.jpg">'),
        ('<img src="/absolute/path/to/image.gif">', '<img src="image.gif">'),
        ('<img src="image.png">', '<img src="image.png">'),  # Already normalized
    ]

    for input_html, expected in test_cases:
        result = normalize_image_paths(input_html)
        assert result == expected, f"Failed for input: {input_html}"
