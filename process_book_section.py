# %%
import os
from litellm import completion 
from pydantic import BaseModel
from prompts.card_creation import CARD_EXTRACTION_PROMPT, STYLE_PROMPT, EXAMPLE_EXTRACTION_PROMPT, MAXI_PROMPT
import json
from runware import Runware, IImageInference
import aiohttp
import asyncio
import base64

from pydantic import BaseModel, Field
from typing import List

class RGB(BaseModel):
    r: int = Field(..., description="Red value (0-255)", le=255)
    g: int = Field(..., description="Green value (0-255)", le=255)
    b: int = Field(..., description="Blue value (0-255)", le=255)

class SectionColor(BaseModel):
    name: str = Field(..., description="The name of the color assigned to this section")
    rgb: RGB

class KeyPassage(BaseModel):
    passage_start: str = Field(..., description="The starting text of the key passage (verbatim quote)")
    passage_end: str = Field(..., description="The ending text of the key passage (verbatim quote)")
    passage_post_process: str = Field(..., description="Keep this field empty, for further processing.")
    chapter: str = Field(..., description="The chapter where this passage appears")

class Chapter(BaseModel):
    chapter_name: str = Field(..., description="The name or title of the chapter")
    chapter_comment: str = Field(..., description="A brief comment or summary about the chapter")
    chapter_start_excerpt: str = Field(..., description="The exact beginning text of the chapter (verbatim)")
    key_quotes: list[str]

class Section(BaseModel):
    section_name: str = Field(..., description="The name of the section from the book")
    section_introduction: str = Field(
        ..., 
        description="Introduction to the key questions of this section and how it connects to the previous section by answering the key questions from that section"
    )
    section_color: SectionColor
    key_passages: list[KeyPassage]
    visual_landscape_description: str = Field(
        ..., 
        description="A detailed description of a landscape that illustrates the section's themes or mood"
    )
    chapters: list[Chapter]
    image_b64: str = Field(..., description="Keep this field empty, for further processing.")

class BookStructure(BaseModel):
    sections: list[Section]

# for the cards
class Card(BaseModel):
    title: str
    description: str
    illustration: str
    quotes: list[str]
    card_type: str

class CardSet(BaseModel):
    card_definitions: list[Card]

def create_book_structure(book: str):
    prompt = MAXI_PROMPT.format(BOOK = book)
    result = completion(
        model="gemini/gemini-2.5-flash-preview-05-20",
        messages=[{"role": "user", "content": prompt}],
        response_format=BookStructure,
        reasoning_effort="medium",
    )

    result_json = result.choices[0].message.content
    book_structure = BookStructure.model_validate_json(result_json)
    return book_structure


def process_book_section(book_section: str, nb_cards: int = 10):
    # Configure the client and tools

    # Compose the prompt by replacing placeholders
    cards_nb, example_nb = int(nb_cards*0.7), nb_cards - int(nb_cards*0.7)

    prompt = CARD_EXTRACTION_PROMPT.format(
        NB_CARD=cards_nb,
        BOOK_SECTION=book_section
    )

    example_prompt = EXAMPLE_EXTRACTION_PROMPT.format(
        NB_CARD=example_nb,
        BOOK_SECTION=book_section
    )

    # Send request with function declarations
    cards_rep = completion(
        model="gemini/gemini-2.5-flash-preview-05-20", # gemini-2.5-pro-preview-05-06
        messages=[{"role": "user", "content": prompt}],
        response_format=CardSet,
        reasoning_effort="medium",
    )

    example_rep = completion(
        model="gemini/gemini-2.5-flash-preview-05-20",
        messages=[{"role": "user", "content": example_prompt}],
        response_format=CardSet,
        reasoning_effort="medium",
    )

    cards_json = cards_rep.choices[0].message.content
    cards_set = CardSet.model_validate_json(cards_json)

    examples_json = example_rep.choices[0].message.content
    examples_set = CardSet.model_validate_json(examples_json)

    cards_set.card_definitions += examples_set.card_definitions

    print(cards_set.card_definitions)

    print("====")

    print(examples_set.card_definitions)

    return cards_set


from openai import AsyncOpenAI

async def generate_image_openai(prompt: str, index: int):
    client = AsyncOpenAI()

    img = await client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        n=1,
        size="1024x1024",
        quality="low",
    )

    return img.data.b64_json

async def generate_image(prompt: str, index: int = -1) -> str:
    """
    Generate an image based on the visual description of an analogy.
    
    Args:
        visual_description: The visual description to use as a prompt
        
    Returns:
        Base64 encoded image string
    """
    runware = Runware(api_key=os.getenv("RUNWARE_API_KEY"))
    await runware.connect()
    
    request_image = IImageInference(
        positivePrompt=prompt,
        model="runware:101@1",
        numberResults=1,
        negativePrompt="Text, label, diagram, blurry, low quality, distorted",
        height=768, # 740
        width=384, # 394
    )
    
    images = await runware.imageInference(requestImage=request_image)
    print(f"Generated image {index}")
    if images:
        # Download the image asynchronously using aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(images[0].imageURL) as response:
                if response.status == 200:
                    content = await response.read()
                    image_base64 = base64.b64encode(content).decode('utf-8')
                    return image_base64
    return "No image generated"

async def generate_images(prompts: list[str]) -> list[str]:
    tasks = [generate_image(prompt, index) for index, prompt in enumerate(prompts)]
    return await asyncio.gather(*tasks)

def generate_images_sync(prompts: list[str]) -> list[str]:
    return asyncio.run(generate_images(prompts))


class StyleList(BaseModel):
    style_list: list[str]

def add_image_styles(cards: CardSet):
    """Add a style instruction to all the illustration description of the cards using STYLE_PROMPT"""
    # Convert cards to JSON format for the prompt
    cards_json = "\n\n----\n\n".join([f"CARD #{i}\n" + str(card) for i,card in enumerate(cards.card_definitions)])
    
    # Compose the prompt by replacing the placeholder
    prompt = STYLE_PROMPT.format(CARDS=cards_json, NB_CARD=len(cards.card_definitions))

    # Send request to get styled prompts
    response = completion(
        model="gemini/gemini-2.5-flash-preview-05-20",
        messages=[{"role": "user", "content": prompt}],
        response_format=StyleList,
        reasoning_effort="medium"
    )

    style_list = StyleList.model_validate_json(response.choices[0].message.content).style_list
    print(style_list)
    for i, card in enumerate(cards.card_definitions):
        print(i)
        card.illustration += " " + style_list[i]
    
    # Return the list of styled prompts


# %%

with open("books/scout.html", "r") as f:
    book = f.read()

book_structure = create_book_structure(book)
# %%
# Pretty print the book structure
print("\nBook Structure:")
print(json.dumps(book_structure.model_dump(), indent=2))

# %%



# %%
with open("book_section.md", "r") as f:
    book_section = f.read()

# Process the book section

cards = process_book_section(book_section, nb_cards=10)


# %%

add_image_styles(cards)

# %%
# Generate images for each card


illustration_prompts = [card.illustration for card in cards.card_definitions]
image_base64_list = await generate_images(illustration_prompts)

name_file = "scout_mindset_rect"
# Create JSONL file with cards and their images
with open(f"{name_file}.jsonl", "w") as f:
    for card, image_base64 in zip(cards.card_definitions, image_base64_list):
        card_dict = card.model_dump()
        card_dict["image_base64"] = image_base64
        f.write(json.dumps(card_dict) + "\n")

print(f"Generated {len(cards.card_definitions)} cards with images and saved to cards_with_images.jsonl")


# %%

def split_book_into_sections(book: str, book_structure: BookStructure) -> list[str]:
    """
    Split the book into sections using the chapter_start_excerpt of the first chapter in each section as delimiter.
    
    Args:
        book: The full book text
        book_structure: The BookStructure object containing section information
        
    Returns:
        list[str]: List of section texts
    """
    sections = []
    current_pos = 0
    
    for section in book_structure.sections:
        if not section.chapters:  # Skip if section has no chapters
            continue
            
        # Get the start excerpt of the first chapter in the section
        first_chapter_start = section.chapters[0].chapter_start_excerpt
        
        # Find the position of this excerpt in the book
        start_pos = book.find(first_chapter_start, current_pos)
        if start_pos == -1:  # If excerpt not found, skip this section
            print(f"Warning: Could not find start excerpt for section: {section.section_name}")
            continue
            
        # If this is not the first section, update the current position
        if current_pos > 0:
            current_pos = start_pos
            
        # Find the start of the next section (or end of book)
        next_section_start = len(book)
        for next_section in book_structure.sections:
            if next_section.sections.index(section) < len(book_structure.sections) - 1:
                next_section_start = book.find(next_section.chapters[0].chapter_start_excerpt, start_pos + 1)
                if next_section_start != -1:
                    break
        
        # Extract the section text
        section_text = book[current_pos:next_section_start].strip()
        sections.append(section_text)
        
        # Update current position for next iteration
        current_pos = next_section_start
    
    return sections

# Example usage:
# sections = split_book_into_sections(book, book_structure)
# for i, section in enumerate(sections):
#     print(f"\nSection {i+1}:")
#     print(section[:200] + "...")  # Print first 200 chars of each section

# %%
