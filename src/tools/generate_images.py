"""Generate card images via Runware, with a file cache keyed by prompt hash."""

import asyncio
import hashlib
import json
import os
import logging
from pathlib import Path
from typing import cast

import aiohttp
from runware import IImage, IImageInference, Runware

log = logging.getLogger("bb.generate_images")
RUNWARE_MODEL = "runware:101@1"
_NEGATIVE_PROMPT = "Text, label, diagram, blurry, low quality, distorted"

# Default image size (height, width) for card illustrations.
# Landscape-oriented to fit the left/right image slot in card templates.
DEFAULT_SIZE: tuple[int, int] = (512, 768)


def _prompt_cache_path(prompt: str, cache_dir: Path) -> Path:
    """Return the cache path for a given prompt: cache_dir/{sha256(prompt)}.png"""
    digest = hashlib.sha256(prompt.encode()).hexdigest()
    return cache_dir / f"{digest}.png"


async def _generate_image_async(prompt: str, size: tuple[int, int], cache_dir: Path) -> Path:
    """Download one image from Runware, saving it as a PNG in cache_dir."""
    cache_path = _prompt_cache_path(prompt, cache_dir)
    if cache_path.exists():
        return cache_path

    api_key = os.environ["RUNWARE_API_KEY"]
    runware = Runware(api_key=api_key)
    await runware.connect()

    request_image = IImageInference(
        positivePrompt=prompt,
        model=RUNWARE_MODEL,
        numberResults=1,
        negativePrompt=_NEGATIVE_PROMPT,
        height=size[0],
        width=size[1],
    )
    images = await runware.imageInference(requestImage=request_image)

    if not isinstance(images, list) or not images:
        raise RuntimeError(f"Runware returned no images for prompt: {prompt!r}")

    first_image = cast(IImage, images[0])
    image_url = first_image.imageURL
    if image_url is None:
        raise RuntimeError(f"Runware returned image without URL for prompt: {prompt!r}")

    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            response.raise_for_status()
            content = await response.read()

    cache_path.write_bytes(content)
    return cache_path


def generate_image(prompt: str, size: tuple[int, int], cache_dir: Path) -> Path:
    """
    Generate a single image from a text prompt.

    Uses a file cache: if `cache_dir/{sha256(prompt)}.png` exists, return it directly.
    Otherwise calls the Runware API and saves the result.

    Returns the path to the cached PNG file.
    """
    return asyncio.run(_generate_image_async(prompt, size, cache_dir))


def generate_images_for_cards(
    cards_json_path: Path,
    images_dir: Path,
    size: tuple[int, int] = DEFAULT_SIZE,
) -> None:
    """
    Generate and cache images for every card in cards.json that lacks one.

    Reads `image_description` from each card, calls the Runware API in parallel,
    and writes the resulting absolute path back into cards.json under `image_path`.
    Skips cards that already have `image_path` set.
    """
    cards: list[dict] = json.loads(cards_json_path.read_text(encoding="utf-8"))

    async def _run_all() -> None:
        tasks = []
        indices = []
        for i, card in enumerate(cards):
            desc = card.get("image_description")
            if desc and not card.get("image_path"):
                tasks.append(_generate_image_async(desc, size, images_dir))
                indices.append(i)

        if not tasks:
            return

        log.info(f"Generating {len(tasks)} image(s)…")
        paths = await asyncio.gather(*tasks)
        for i, path in zip(indices, paths):
            cards[i]["image_path"] = str(path)

    asyncio.run(_run_all())
    cards_json_path.write_text(json.dumps(cards, indent=2, ensure_ascii=False), encoding="utf-8")
