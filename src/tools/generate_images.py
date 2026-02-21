"""
Generate card images via Runware, with a persistent file cache.

Image resolution pattern
------------------------
Images are never stored inside cards.json. Instead, the path is always derived
deterministically from the card's image_description:

    image_cache_path(description, images_dir)
    → images_dir / f"{sha256(description)}.png"

This function is the shared contract between generation and rendering:

  1. generate_images_for_cards()  — calls _fetch_and_cache() for each card whose
                                    cache file does not yet exist.
  2. render_template.py           — calls image_cache_path() at render time to
                                    locate the PNG and embed it as base64.

The cache lives in OUT/images/ (OutDir.images_dir) so it persists across runs
and is shared when the same description appears in multiple sessions.
"""

import asyncio
import hashlib
import logging
import os
from pathlib import Path
from typing import cast

import aiohttp
from pydantic import TypeAdapter
from runware import IImage, IImageInference, Runware

from schemas import Card

log = logging.getLogger("bb.generate_images")
RUNWARE_MODEL = "runware:101@1"
_NEGATIVE_PROMPT = "Text, label, diagram, blurry, low quality, distorted"

# Default image size (height, width) for card illustrations.
# Landscape-oriented to fit the left/right image slot in card templates.
DEFAULT_SIZE: tuple[int, int] = (512, 768)

_cards_adapter = TypeAdapter(list[Card])


def image_cache_path(description: str, images_dir: Path) -> Path:
    """Return the deterministic cache path for an image: images_dir/{sha256(description)}.png

    This is the single source of truth for where any image lives on disk.
    Both the generator and the renderer use this function — no path is ever
    stored in cards.json.
    """
    digest = hashlib.sha256(description.encode()).hexdigest()
    return images_dir / f"{digest}.png"


async def _fetch_and_cache(description: str, size: tuple[int, int], images_dir: Path) -> None:
    """Call Runware for one image and save it to the cache. No-op if already cached."""
    cache_path = image_cache_path(description, images_dir)
    if cache_path.exists():
        return

    api_key = os.environ["RUNWARE_API_KEY"]
    runware = Runware(api_key=api_key)
    await runware.connect()

    request_image = IImageInference(
        positivePrompt=description,
        model=RUNWARE_MODEL,
        numberResults=1,
        negativePrompt=_NEGATIVE_PROMPT,
        height=size[0],
        width=size[1],
    )
    images = await runware.imageInference(requestImage=request_image)

    if not isinstance(images, list) or not images:
        raise RuntimeError(f"Runware returned no images for prompt: {description!r}")

    first_image = cast(IImage, images[0])
    image_url = first_image.imageURL
    if image_url is None:
        raise RuntimeError(f"Runware returned image without URL for prompt: {description!r}")

    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            response.raise_for_status()
            content = await response.read()

    cache_path.write_bytes(content)


def generate_image(description: str, size: tuple[int, int], images_dir: Path) -> Path:
    """
    Ensure the image for a description exists in images_dir and return its path.

    Cache key is SHA256(description), so the same prompt always maps to the same file.
    Calls the Runware API only on a cache miss.
    """
    asyncio.run(_fetch_and_cache(description, size, images_dir))
    return image_cache_path(description, images_dir)


def generate_images_for_cards(
    cards_json_path: Path,
    images_dir: Path,
    size: tuple[int, int] = DEFAULT_SIZE,
) -> None:
    """
    Ensure images exist for every card in cards.json that has an image_description.

    Images are cached as images_dir/{sha256(description)}.png — no path is stored
    back into cards.json. Use image_cache_path() at render time to resolve the path.
    Skips cards whose image is already cached.
    """
    cards = _cards_adapter.validate_json(cards_json_path.read_bytes())
    descriptions = [
        card.image_description
        for card in cards
        if hasattr(card, "image_description")
        and not image_cache_path(card.image_description, images_dir).exists()
    ]

    if not descriptions:
        return

    async def _run_all() -> None:
        log.info(f"Generating {len(descriptions)} image(s)…")
        await asyncio.gather(*[_fetch_and_cache(d, size, images_dir) for d in descriptions])

    asyncio.run(_run_all())
