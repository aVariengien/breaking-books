# %%
import os
from litellm import completion, acompletion
from pydantic import BaseModel
from prompts.card_creation import CARD_EXTRACTION_PROMPT, STYLE_PROMPT, EXAMPLE_EXTRACTION_PROMPT, MAXI_PROMPT
import json
from runware import Runware, IImageInference
import aiohttp
import asyncio
import base64
from openai import AsyncOpenAI

from pydantic import BaseModel, Field
from typing import List

os.environ["GEMINI_API_KEY"] = "AIzaSyDQTEPI1STR2RhYBENaPkVvAdjWnsEHyds"

MODEL_NAME = "gemini/gemini-2.5-flash-preview-05-20" # gemini/gemini-2.5-flash-preview-05-20

class SectionColor(BaseModel):
    name: str = Field(..., description="The name of the color assigned to this section")
    html_color: str = Field(..., description="The html hex code of the color like #1A2B3C")

class KeyPassage(BaseModel):
    passage_start_tag: str = Field(..., description="The tag id value of the start of the passage. Example value: 'tag-342'.")
    passage_end_tag: str = Field(..., description="The tag id value of the end of the passage. Example value: 'tag-342'.")
    passage_post_process: str = Field(..., description="Keep this field empty, for further processing.")
    chapter: str = Field(..., description="The chapter where this passage appears")

class Chapter(BaseModel):
    chapter_name: str = Field(..., description="The name or title of the chapter, add the name as it is in the table of content")
    chapter_comment: str = Field(..., description="A brief comment or summary about the chapter")
    chapter_start_tag: str = Field(..., description="The tag id value of the start of the chapter. Example value: 'tag-342'.")
    chapter_end_tag: str = Field(..., description="The tag id value of the end of the chapter. Example value: 'tag-342'.")
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
    card_color: str = Field(..., description="Keep this field empty, for further processing.")

class CardSet(BaseModel):
    card_definitions: list[Card]

def create_book_structure(book: str):
    prompt = MAXI_PROMPT.format(BOOK = book)
    result = completion(
        model=MODEL_NAME,
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
        model=MODEL_NAME, # gemini-2.5-pro-preview-05-06
        messages=[{"role": "user", "content": prompt}],
        response_format=CardSet,
        reasoning_effort="medium",
    )

    example_rep = completion(
        model=MODEL_NAME,
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



async def process_book_section_async(book_section: str, nb_cards: int = 10) -> CardSet:
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

    # Send requests concurrently with function declarations
    cards_rep, example_rep = await asyncio.gather(
        acompletion(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            response_format=CardSet,
            reasoning_effort="medium",
        ),
        acompletion(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": example_prompt}],
            response_format=CardSet,
            reasoning_effort="medium",
        )
    )

    cards_json = cards_rep.choices[0].message.content
    cards_set = CardSet.model_validate_json(cards_json)

    examples_json = example_rep.choices[0].message.content
    examples_set = CardSet.model_validate_json(examples_json)

    cards_set.card_definitions += examples_set.card_definitions

    return cards_set

async def process_book_sections_async(sections: list[str], nb_cards: int = 10) -> CardSet:
    """
    Process multiple book sections concurrently and combine their cards.
    
    Args:
        sections: List of book section texts to process
        nb_cards: Number of cards to generate per section
        
    Returns:
        CardSet: Combined set of cards from all sections
    """
    # Process all sections concurrently
    card_sets = await asyncio.gather(
        *[process_book_section_async(section, nb_cards) for section in sections]
    )
    
    # Combine all card sets into one
    combined_cards = CardSet(card_definitions=[])
    for card_set in card_sets:
        combined_cards.card_definitions.extend(card_set.card_definitions)
    
    return combined_cards




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

async def generate_image(prompt: str, image_size: tuple[int,int], index: int = -1) -> str:
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
        height=image_size[0], #768, # 740
        width=image_size[1], #384, # 394
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

async def generate_images(prompts: list[str], image_size: tuple[int,int]) -> list[str]:
    tasks = [generate_image(prompt, image_size, index) for index, prompt in enumerate(prompts)]
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
        model=MODEL_NAME,
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

with open("books/measure.html", "r") as f:
    book = f.read()


book_structure = create_book_structure(book)
# %%
# Pretty print the book structure
print("\nBook Structure:")
print(json.dumps(book_structure.model_dump(), indent=2))

# Save the book structure to a JSON file


# %%

# Generate landscape images for each section
landscape_prompts = [section.visual_landscape_description for section in book_structure.sections]
landscape_images = await generate_images(landscape_prompts, image_size=(384, 640))

# Add the generated images to each section
for section, image_base64 in zip(book_structure.sections, landscape_images):
    section.image_b64 = image_base64

print("Generated landscape images for all sections")

# %% process excerpt

def process_passages(book: str, book_structure: BookStructure):
    """Process passages in the book structure by extracting content between tags"""
    for section in book_structure.sections:
        for passage in section.key_passages:
            # Find the start and end positions
            start_tag = f'id="{passage.passage_start_tag}"'
            end_tag = f'id="{passage.passage_end_tag}"'
            
            start_idx = book.find(start_tag)
            end_idx = book.find(end_tag)
            
            if start_idx == -1 or end_idx == -1:
                print(f"Warning: Could not find tags for passage in section {section.section_name}")
                continue
                
            # Find the previous < before the start tag
            while start_idx > 0 and book[start_idx] != '<':
                start_idx -= 1
                
            # Find the previous < before the end tag
            while end_idx > 0 and book[end_idx] != '<':
                end_idx -= 1
                
            # Extract the passage content
            passage.passage_post_process = book[start_idx:end_idx]


# Process the passages
process_passages(book, book_structure)


# %%
def split_book_into_sections(book: str, book_structure: BookStructure) -> list[str]:
    """
    Split a book into sections based on the chapter tags in the book structure.
    
    Args:
        book: The full book text in HTML format
        book_structure: The BookStructure object containing section and chapter information
        
    Returns:
        list[str]: List of section texts, where each section contains all chapters within it
    """
    sections = []
    
    for section in book_structure.sections:
        # Get the first and last chapter tags for this section
        first_chapter = section.chapters[0]
        last_chapter = section.chapters[-1]
        
        # Find the start and end positions in the book text
        start_tag = f'id="{first_chapter.chapter_start_tag}"'
        end_tag = f'id="{last_chapter.chapter_end_tag}"'
        
        start_idx = book.find(start_tag)
        end_idx = book.find(end_tag) + len(end_tag)
        
        if start_idx == -1 or end_idx == -1:
            raise ValueError(f"Could not find chapter tags for section {section.section_name}")
            
        # Extract the section text
        section_text = book[start_idx:end_idx]
        sections.append(section_text)
    
    return sections

sections = split_book_into_sections(book, book_structure)

# %%
print("\nSection lengths:")
for i, section in enumerate(sections):
    print(f"Section {i+1}: {len(section)} characters")

# %%
assert len(sections) == len(book_structure.sections)

all_cards = CardSet(card_definitions=list())
total_chars = sum(len(section) for section in sections)

total_cards = 40

for section_idx, section_text in enumerate(sections):
    card_set = process_book_section(section_text, nb_cards=int(total_cards*len(section_text)/total_chars))
    print(f"section {section_idx} processed.")
    add_image_styles(card_set)
    print(f"section {section_idx} style added.")
    for card in card_set.card_definitions:
        card.card_color = book_structure.sections[section_idx].section_color
        all_cards.card_definitions.append(card)

# %%
# Generate images for each card


illustration_prompts = [card.illustration for card in all_cards.card_definitions]
image_base64_list = await generate_images(illustration_prompts, image_size=(768, 384))

print(f"Generated {len(all_cards.card_definitions)} cards with images and saved to cards_with_images.jsonl")


# %%
name_file = "measure"
# Create JSONL file with cards and their images
with open(f"{name_file}.jsonl", "w") as f:
    for card, image_base64 in zip(all_cards.card_definitions, image_base64_list):
        card_dict = card.model_dump()
        card_dict["image_base64"] = image_base64
        f.write(json.dumps(card_dict) + "\n")

with open(f"book_structure_{name_file}.json", "w") as f:
    json.dump(book_structure.model_dump(), f, indent=2)


# %%

# Example usage:
# sections = split_book_into_sections(book, book_structure)
# for i, section in enumerate(sections):
#     print(f"\nSection {i+1}:")
#     print(section[:200] + "...")  # Print first 200 chars of each section

# %%



# %%
