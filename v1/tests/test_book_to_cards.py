import copy
from pathlib import Path

import pytest

from src.book_to_cards import (
    analyze_book_structure,
    generate_cards_from_sections,
    generate_images_for_game,
)


def test_analyze_book_structure():
    """Test that analyze_book_structure returns valid BookStructure with expected attributes."""
    # Load the test HTML file
    html_file = Path("tests/fixtures/meditations.html")
    book_html = html_file.read_text()

    # Call the function
    book_structure = analyze_book_structure(book_html)

    # Test basic structure
    assert book_structure.sections, "BookStructure should have sections"
    assert len(book_structure.sections) > 0, "Should have at least one section"

    # Test section attributes
    for section in book_structure.sections:
        assert section.section_name, "Each section should have a name"
        assert isinstance(section.section_name, str), "Section name should be a string"
        assert len(section.section_name.strip()) > 0, "Section name should not be empty"

        assert section.chapters, "Each section should have chapters"
        assert len(section.chapters) > 0, "Each section should have at least one chapter"

        assert section.key_passages, "Each section should have key passages"

        # Test section color
        assert section.section_color.name, "Section should have color name"
        assert section.section_color.html_color.startswith("#"), "Should have valid hex color"

        # Test visual description
        assert section.visual_landscape_description, "Should have landscape description"
        assert (
            len(section.visual_landscape_description.strip()) > 10
        ), "Description should be meaningful"

    # Test chapter attributes
    for section in book_structure.sections:
        for chapter in section.chapters:
            assert chapter.chapter_name, "Each chapter should have a name"
            assert chapter.chapter_start_tag.startswith(
                "tag-"
            ), "Start tag should follow expected format"
            assert chapter.chapter_end_tag.startswith(
                "tag-"
            ), "End tag should follow expected format"
            assert isinstance(chapter.key_quotes, list), "Key quotes should be a list"

    # Test passage extraction
    passages_with_content = 0
    for section in book_structure.sections:
        for passage in section.key_passages:
            assert passage.passage_start_tag.startswith(
                "tag-"
            ), "Passage start tag should follow format"
            assert passage.passage_end_tag.startswith(
                "tag-"
            ), "Passage end tag should follow format"
            assert passage.chapter, "Passage should have chapter reference"

            # Check if HTML extraction worked
            if passage.passage_post_process:
                passages_with_content += 1
                assert "<" in passage.passage_post_process, "Extracted content should contain HTML"
                assert ">" in passage.passage_post_process, "Extracted content should contain HTML"

    # At least some passages should have extracted content
    assert passages_with_content > 0, "At least some passages should have extracted HTML content"

    print(
        f"✓ Test passed with {len(book_structure.sections)} sections, {passages_with_content} passages with content"
    )


@pytest.mark.asyncio
async def test_generate_cards_from_sections():
    """Test that generate_cards_from_sections creates valid cards with proper distribution."""
    # Load the test HTML file and get structure
    html_file = Path("tests/fixtures/meditations.html")
    book_html = html_file.read_text()
    book_structure = analyze_book_structure(book_html)

    total_cards = 20
    card_set = await generate_cards_from_sections(book_html, book_structure, total_cards)

    assert len(card_set.card_definitions) > total_cards - 5, "Should have at least one card"
    assert (
        len(card_set.card_definitions) <= total_cards + 5
    ), "Should not exceed requested cards by much"

    # Test card attributes
    for card in card_set.card_definitions:
        assert card.title.strip(), "Title should not be empty"
        assert card.description.strip(), "Description should not be empty"

        assert card.illustration.strip(), "Illustration should not be empty"
        assert (
            len(card.illustration) < 2000
        ), "Illustration should be less than 2000 characters. Should be the description, not the base64 image."
        # Image should be empty string initially (filled later by generate_images_for_game)
        assert not card.image_base64, "Image should be empty initially"

        assert card.card_color.startswith("#"), "Card color should be a valid hex color"

    # Test card distribution across sections
    section_colors = {section.section_color.html_color for section in book_structure.sections}
    card_colors = {card.card_color for card in card_set.card_definitions}

    assert card_colors == section_colors, "All card colors should match section colors"

    # Test card type distribution
    card_types = [card.card_type for card in card_set.card_definitions]
    type_counts = {card_type: card_types.count(card_type) for card_type in set(card_types)}

    print(
        f"✓ Test passed with {len(card_set.card_definitions)} cards, {len(card_colors)} sections, types: {type_counts}"
    )


@pytest.mark.asyncio
async def test_generate_images_for_game():
    """Test that generate_images_for_game adds images without changing other attributes."""
    # Load the test HTML file and get structure
    html_file = Path("tests/fixtures/meditations.html")
    book_html = html_file.read_text()
    book_structure = analyze_book_structure(book_html)

    # Generate cards for testing (same as other test to use cache)
    total_cards = 20  # Use same number as other test for cached results
    original_cards = await generate_cards_from_sections(book_html, book_structure, total_cards)
    original_book_structure = copy.deepcopy(book_structure)

    # Create deep copies to compare against later
    original_cards_copy = copy.deepcopy(original_cards)
    original_structure_copy = copy.deepcopy(original_book_structure)

    # Call the function
    updated_cards, updated_structure = await generate_images_for_game(
        original_cards, original_book_structure
    )

    # Test return values
    assert updated_cards is not None, "Should return CardSet"
    assert updated_structure is not None, "Should return BookStructure"
    assert updated_cards == original_cards, "Should return the same CardSet object"
    assert (
        updated_structure == original_book_structure
    ), "Should return the same BookStructure object"

    # Test that all cards now have images
    for i, card in enumerate(updated_cards.card_definitions):
        original_card = original_cards_copy.card_definitions[i]

        # Image should now be populated
        assert card.image_base64, "Each card should have image_base64 populated"
        assert isinstance(card.image_base64, str), "Image should be a string"
        assert len(card.image_base64) > 100, "Image base64 should be substantial"

        # All other attributes should remain the same
        assert card.title == original_card.title, "Title should not change"
        assert card.description == original_card.description, "Description should not change"
        assert card.card_type == original_card.card_type, "Card type should not change"
        assert card.card_color == original_card.card_color, "Card color should not change"
        assert card.quotes == original_card.quotes, "Quotes should not change"

        # Illustration might have visual style added
        assert len(card.illustration) >= len(
            original_card.illustration
        ), "Illustration should be enhanced with style"
        assert (
            original_card.illustration in card.illustration
        ), "Original illustration should be preserved"

    # Test that all sections now have landscape images
    for i, section in enumerate(updated_structure.sections):
        original_section = original_structure_copy.sections[i]

        # Image should now be populated
        assert section.image_base64, "Each section should have image_base64 populated"
        assert isinstance(section.image_base64, str), "Section image should be a string"
        assert len(section.image_base64) > 100, "Section image base64 should be substantial"

        # All other section attributes should remain the same
        assert (
            section.section_name == original_section.section_name
        ), "Section name should not change"
        assert (
            section.section_introduction == original_section.section_introduction
        ), "Section intro should not change"
        assert (
            section.section_color == original_section.section_color
        ), "Section color should not change"
        assert (
            section.visual_landscape_description == original_section.visual_landscape_description
        ), "Landscape description should not change"
        assert (
            section.key_passages == original_section.key_passages
        ), "Key passages should not change"
        assert section.chapters == original_section.chapters, "Chapters should not change"

    # Basic validation of base64 format (should contain common base64 characters)
    all_images = [card.image_base64 for card in updated_cards.card_definitions] + [
        section.image_base64 for section in updated_structure.sections
    ]

    for image_b64 in all_images:
        # Should contain typical base64 characters
        assert any(
            c in image_b64
            for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        ), "Should contain base64 characters"

    print(
        f"✓ Test passed with {len(updated_cards.card_definitions)} card images and {len(updated_structure.sections)} section images generated"
    )
