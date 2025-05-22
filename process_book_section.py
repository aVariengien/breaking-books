# %%
import os
from litellm import completion 
from pydantic import BaseModel
from prompts.card_creation import CARD_EXTRACTION_PROMPT, STYLE_PROMPT
import json
from runware import Runware, IImageInference
import aiohttp
import asyncio
import base64

class Card(BaseModel):
    title: str
    description: str
    illustration: str
    quotes: list[str]

class CardSet(BaseModel):
    card_definitions: list[Card]

def process_book_section(book_section: str, nb_cards: int = 10):
    # Configure the client and tools

    # Compose the prompt by replacing placeholders
    prompt = CARD_EXTRACTION_PROMPT.format(
        NB_CARD=nb_cards,
        BOOK_SECTION=book_section
    )

    # Send request with function declarations
    response = completion(
        model="gemini/gemini-2.5-flash-preview-05-20",
        messages=[{"role": "user", "content": prompt}],
        response_format=CardSet,
        reasoning_effort="medium",
    )
    return response

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
        negativePrompt="Text, diagram, blurry, low quality, distorted",
        height=512,
        width=512,
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
with open("book_section.md", "r") as f:
    book_section = f.read()

# Process the book section

result = process_book_section(book_section, nb_cards=15)
cards_json = result.choices[0].message.content
cards = CardSet.model_validate_json(cards_json)

# %%


add_image_styles(cards)


# %%
# Generate images for each card
illustration_prompts = [card.illustration for card in cards.card_definitions]
image_base64_list = await generate_images(illustration_prompts)


name_file = "precipice_part2_with_style"
# Create JSONL file with cards and their images
with open(f"{name_file}.jsonl", "w") as f:
    for card, image_base64 in zip(cards.card_definitions, image_base64_list):
        card_dict = card.model_dump()
        card_dict["image_base64"] = image_base64
        f.write(json.dumps(card_dict) + "\n")

print(f"Generated {len(cards.card_definitions)} cards with images and saved to cards_with_images.jsonl")

# %%

