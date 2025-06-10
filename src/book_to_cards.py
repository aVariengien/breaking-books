import asyncio
import base64
import json
import os
from pathlib import Path

import aiohttp
from litellm import acompletion, completion
from pydantic import BaseModel, Field
from runware import IImageInference, Runware

from prompts.card_creation import (
    CARD_EXTRACTION_PROMPT,
    EXAMPLE_EXTRACTION_PROMPT,
    MAXI_PROMPT,
    STYLE_PROMPT,
)

# Configuration constants
MODEL_NAME = "gemini/gemini-2.5-flash-preview-05-20"
CARD_IMAGE_SIZE = (768, 384)
LANDSCAPE_IMAGE_SIZE = (384, 640)
RUNWARE_MODEL = "runware:101@1"
CONCEPT_CARD_RATIO = 0.7  # 70% concept cards, 30% example cards


# Data models
class SectionColor(BaseModel):
    name: str = Field(..., description="The name of the color assigned to this section")
    html_color: str = Field(..., description="The html hex code of the color like #1A2B3C")


class KeyPassage(BaseModel):
    passage_start_tag: str = Field(
        ..., description="The tag id value of the start of the passage. Example value: 'tag-342'."
    )
    passage_end_tag: str = Field(
        ..., description="The tag id value of the end of the passage. Example value: 'tag-342'."
    )
    passage_post_process: str = Field(
        ..., description="Keep this field empty, for further processing."
    )
    chapter: str = Field(..., description="The chapter where this passage appears")


class Chapter(BaseModel):
    chapter_name: str = Field(
        ...,
        description="The name or title of the chapter, add the name as it is in the table of content",
    )
    chapter_comment: str = Field(..., description="A brief comment or summary about the chapter")
    chapter_start_tag: str = Field(
        ..., description="The tag id value of the start of the chapter. Example value: 'tag-342'."
    )
    chapter_end_tag: str = Field(
        ..., description="The tag id value of the end of the chapter. Example value: 'tag-342'."
    )
    key_quotes: list[str]


class Section(BaseModel):
    section_name: str = Field(..., description="The name of the section from the book")
    section_introduction: str = Field(
        ...,
        description="Introduction to the key questions of this section and how it connects to the previous section by answering the key questions from that section",
    )
    section_color: SectionColor
    key_passages: list[KeyPassage]
    visual_landscape_description: str = Field(
        ...,
        description="A detailed description of a landscape that illustrates the section's themes or mood",
    )
    chapters: list[Chapter]
    image_b64: str = Field(..., description="Keep this field empty, for further processing.")


class BookStructure(BaseModel):
    sections: list[Section]


class Card(BaseModel):
    title: str
    description: str
    illustration: str
    quotes: list[str]
    card_type: str
    card_color: str = Field(..., description="Keep this field empty, for further processing.")


class CardSet(BaseModel):
    card_definitions: list[Card]


class StyleList(BaseModel):
    style_list: list[str]


# Core pipeline functions


def analyze_book_structure(book_html: str) -> BookStructure:
    """Analyze book HTML and return structured breakdown with sections, chapters, and passages."""
    # Create initial structure
    prompt = MAXI_PROMPT.format(BOOK=book_html)
    result = completion(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format=BookStructure,
        reasoning_effort="medium",
    )

    book_structure = BookStructure.model_validate_json(result.choices[0].message.content)

    # Process passages by extracting content between tags
    for section in book_structure.sections:
        for passage in section.key_passages:
            start_tag = f'id="{passage.passage_start_tag}"'
            end_tag = f'id="{passage.passage_end_tag}"'

            start_idx = book_html.find(start_tag)
            end_idx = book_html.find(end_tag)

            if start_idx == -1 or end_idx == -1:
                print(f"Warning: Could not find tags for passage in section {section.section_name}")
                continue

            # Find the previous < before the start tag
            while start_idx > 0 and book_html[start_idx] != "<":
                start_idx -= 1

            # Find the previous < before the end tag
            while end_idx > 0 and book_html[end_idx] != "<":
                end_idx -= 1

            passage.passage_post_process = book_html[start_idx:end_idx]

    return book_structure


async def generate_cards_from_sections(
    book_html: str, book_structure: BookStructure, total_cards: int
) -> CardSet:
    """Generate game cards from book sections with proportional distribution."""
    # Split book into sections
    sections = _split_book_into_sections(book_html, book_structure)

    # Calculate cards per section based on content length
    cards_per_section = _calculate_cards_per_section(sections, total_cards)

    # Generate cards for each section concurrently
    section_card_sets = await asyncio.gather(
        *[
            generate_section_cards_async(section_text, num_cards)
            for section_text, num_cards in zip(sections, cards_per_section)
        ]
    )

    # Combine all cards and assign section colors
    all_cards = CardSet(card_definitions=[])
    for section_idx, card_set in enumerate(section_card_sets):
        section_color = book_structure.sections[section_idx].section_color
        for card in card_set.card_definitions:
            card.card_color = section_color
            all_cards.card_definitions.append(card)
        print(f"Section {section_idx} processed with {len(card_set.card_definitions)} cards")

    return all_cards


async def generate_images_for_game(
    cards: CardSet, book_structure: BookStructure
) -> tuple[CardSet, BookStructure]:
    """Generate images for cards and landscape sections, adding visual styles to cards."""
    # Add visual styles to card illustrations
    _add_visual_styles_to_cards(cards)

    # Generate card images and landscape images concurrently
    card_prompts = [card.illustration for card in cards.card_definitions]
    landscape_prompts = [
        section.visual_landscape_description for section in book_structure.sections
    ]

    card_images, landscape_images = await asyncio.gather(
        _generate_images_async(card_prompts, CARD_IMAGE_SIZE),
        _generate_images_async(landscape_prompts, LANDSCAPE_IMAGE_SIZE),
    )

    # Assign images to cards and sections
    for card, image_b64 in zip(cards.card_definitions, card_images):
        card.illustration = image_b64

    for section, image_b64 in zip(book_structure.sections, landscape_images):
        section.image_b64 = image_b64

    print(
        f"Generated {len(cards.card_definitions)} card images and {len(book_structure.sections)} landscape images"
    )
    return cards, book_structure


def save_game_data(cards: CardSet, book_structure: BookStructure, filename: str):
    """Save cards as JSONL and book structure as JSON."""
    # Save cards with images as JSONL
    cards_file = Path(f"{filename}.jsonl")
    with cards_file.open("w") as f:
        for card in cards.card_definitions:
            card_dict = card.model_dump()
            f.write(json.dumps(card_dict) + "\n")

    # Save book structure as JSON
    structure_file = Path(f"book_structure_{filename}.json")
    with structure_file.open("w") as f:
        json.dump(book_structure.model_dump(), f, indent=2)

    print(f"Saved {len(cards.card_definitions)} cards to {cards_file}")
    print(f"Saved book structure to {structure_file}")

    return cards_file, structure_file


async def generate_section_cards_async(section_text: str, num_cards: int) -> CardSet:
    """Generate concept and example cards for a single section."""
    concept_cards = int(num_cards * CONCEPT_CARD_RATIO)
    example_cards = num_cards - concept_cards

    concept_prompt = CARD_EXTRACTION_PROMPT.format(NB_CARD=concept_cards, BOOK_SECTION=section_text)

    example_prompt = EXAMPLE_EXTRACTION_PROMPT.format(
        NB_CARD=example_cards, BOOK_SECTION=section_text
    )

    # Generate both types of cards concurrently
    concept_response, example_response = await asyncio.gather(
        acompletion(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": concept_prompt}],
            response_format=CardSet,
            reasoning_effort="medium",
        ),
        acompletion(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": example_prompt}],
            response_format=CardSet,
            reasoning_effort="medium",
        ),
    )

    # Parse and combine card sets
    concept_cards = CardSet.model_validate_json(concept_response.choices[0].message.content)
    example_cards = CardSet.model_validate_json(example_response.choices[0].message.content)

    concept_cards.card_definitions.extend(example_cards.card_definitions)
    return concept_cards


# Private helper functions


def _split_book_into_sections(book_html: str, book_structure: BookStructure) -> list[str]:
    """Split book HTML into section texts based on chapter boundaries."""
    sections = []

    for section in book_structure.sections:
        first_chapter = section.chapters[0]
        last_chapter = section.chapters[-1]

        start_tag = f'id="{first_chapter.chapter_start_tag}"'
        end_tag = f'id="{last_chapter.chapter_end_tag}"'

        start_idx = book_html.find(start_tag)
        end_idx = book_html.find(end_tag) + len(end_tag)

        if start_idx == -1 or end_idx == -1:
            raise ValueError(f"Could not find chapter tags for section {section.section_name}")

        section_text = book_html[start_idx:end_idx]
        sections.append(section_text)

    return sections


def _calculate_cards_per_section(sections: list[str], total_cards: int) -> list[int]:
    """Calculate proportional card distribution based on section text length."""
    total_chars = sum(len(section) for section in sections)
    return [int(total_cards * len(section) / total_chars) for section in sections]


def _add_visual_styles_to_cards(cards: CardSet):
    """Add visual style instructions to card illustrations using AI."""
    cards_text = "\n\n----\n\n".join(
        [f"CARD #{i}\n{card}" for i, card in enumerate(cards.card_definitions)]
    )

    prompt = STYLE_PROMPT.format(CARDS=cards_text, NB_CARD=len(cards.card_definitions))

    response = completion(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format=StyleList,
        reasoning_effort="medium",
    )

    style_list = StyleList.model_validate_json(response.choices[0].message.content).style_list

    for card, style in zip(cards.card_definitions, style_list):
        card.illustration += f" {style}"


async def _generate_images_async(prompts: list[str], image_size: tuple[int, int]) -> list[str]:
    """Generate images for a list of prompts using Runware API."""
    tasks = [
        _generate_single_image_async(prompt, image_size, i) for i, prompt in enumerate(prompts)
    ]
    return await asyncio.gather(*tasks)


async def _generate_single_image_async(prompt: str, image_size: tuple[int, int], index: int) -> str:
    """Generate a single image using Runware API."""
    runware = Runware(api_key=os.getenv("RUNWARE_API_KEY"))
    await runware.connect()

    request_image = IImageInference(
        positivePrompt=prompt,
        model=RUNWARE_MODEL,
        numberResults=1,
        negativePrompt="Text, label, diagram, blurry, low quality, distorted",
        height=image_size[0],
        width=image_size[1],
    )

    images = await runware.imageInference(requestImage=request_image)
    print(f"Generated image {index}")

    if images:
        async with aiohttp.ClientSession() as session:
            async with session.get(images[0].imageURL) as response:
                if response.status == 200:
                    content = await response.read()
                    return base64.b64encode(content).decode("utf-8")

    return "No image generated"
