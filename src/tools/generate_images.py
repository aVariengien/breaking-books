"""Generate card images via Runware, with a file cache keyed by prompt hash."""

import asyncio
import base64
import hashlib
import os
from pathlib import Path
from typing import cast

import aiohttp
from runware import IImage, IImageInference, Runware

RUNWARE_MODEL = "runware:101@1"
_NEGATIVE_PROMPT = "Text, label, diagram, blurry, low quality, distorted"

# Default image size (height, width) for card illustrations.
# Landscape-oriented to fit the left/right image slot in card templates.
DEFAULT_SIZE: tuple[int, int] = (512, 768)


def _prompt_cache_path(prompt: str, size: tuple[int, int], cache_dir: Path) -> Path:
    """Return the cache path for a given prompt+size: cache_dir/{sha256(prompt + size)}.png"""
    cache_key = f"{prompt}_{size[0]}_{size[1]}"
    digest = hashlib.sha256(cache_key.encode()).hexdigest()
    return cache_dir / f"{digest}.png"


def image_cache_path(image_description: str, size: tuple[int, int], images_dir: Path) -> Path:
    """Return the cache path for an image by its description and size."""
    return _prompt_cache_path(image_description, size, images_dir)


async def _generate_image_async(prompt: str, size: tuple[int, int], cache_dir: Path) -> Path:
    """Download one image from Runware, saving it as a PNG in cache_dir."""
    cache_path = _prompt_cache_path(prompt, size, cache_dir)
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

    if not images or not isinstance(images, list):
        raise RuntimeError(f"Runware returned no images for prompt: {prompt!r}")

    image_list = cast(list[IImage], images)
    first_image = image_list[0]
    image_url = first_image.imageURL
    if not image_url:
        raise RuntimeError(f"Runware image has no URL for prompt: {prompt!r}")

    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            response.raise_for_status()
            content = await response.read()

    cache_path.write_bytes(content)
    return cache_path


def generate_image(prompt: str, size: tuple[int, int], cache_dir: Path) -> Path:
    """
    Generate a single image from a text prompt and size.

    Uses a file cache: if `cache_dir/{sha256(prompt + size)}.png` exists, return it directly.
    Otherwise calls the Runware API and saves the result.

    Returns the path to the cached PNG file.
    """
    return asyncio.run(_generate_image_async(prompt, size, cache_dir))


def get_image_base64(
    prompt: str, images_dir: Path, size: tuple[int, int] = DEFAULT_SIZE
) -> str | None:
    """
    Generate or retrieve a cached image as base64-encoded PNG.

    Can be called from Jinja2 templates to embed images directly.
    Returns the base64 string, or None if generation fails.
    """
    try:
        path = generate_image(prompt, size, images_dir)
        return base64.b64encode(path.read_bytes()).decode()
    except Exception:
        return None
