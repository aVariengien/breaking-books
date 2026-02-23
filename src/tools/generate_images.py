"""Generate card images via Runware or Gemini Flash, with a file cache keyed by prompt hash."""

import asyncio
import base64
import hashlib
import os
from pathlib import Path
from typing import cast

import aiohttp
from runware import IImage, IImageInference, Runware

from lib.constants import GEMINI_DIAGRAM_MODEL, RUNWARE_MODEL

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


_ASPECT_RATIOS = [
    ("1:1", 1.000),
    ("4:3", 1.333),
    ("3:2", 1.500),
    ("5:4", 1.250),
    ("16:9", 1.778),
    ("21:9", 2.333),
    ("2:3", 0.667),
    ("3:4", 0.750),
    ("4:5", 0.800),
    ("9:16", 0.563),
]


def _nearest_aspect_ratio(width: int, height: int) -> str:
    """Return the supported Gemini aspect ratio string closest to the given dimensions."""
    target = width / height
    return min(_ASPECT_RATIOS, key=lambda x: abs(x[1] - target))[0]


def _generate_diagram_gemini(prompt: str, size: tuple[int, int], cache_dir: Path) -> Path:
    """Generate a diagram image using Gemini Flash at the requested size, saving as PNG in cache_dir."""
    from google import genai
    from google.genai import types

    cache_path = _prompt_cache_path(f"gemini:{prompt}", size, cache_dir)
    if cache_path.exists():
        return cache_path

    width, height = size
    aspect_ratio = _nearest_aspect_ratio(width, height)

    framed_prompt = f"{prompt}"

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=GEMINI_DIAGRAM_MODEL,
        contents=framed_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size="1K",
            ),
        ),
    )

    if not response.candidates:
        raise RuntimeError(f"Gemini returned no candidates for prompt: {prompt!r}")
    candidate = response.candidates[0]
    content = candidate.content
    if content is None or content.parts is None:
        raise RuntimeError(f"Gemini returned empty content for prompt: {prompt!r}")

    image_bytes: bytes | None = None
    for part in content.parts:
        if part.inline_data is not None:
            image_bytes = part.inline_data.data
            break

    if image_bytes is None:
        raise RuntimeError(f"Gemini returned no image for prompt: {prompt!r}")

    cache_path.write_bytes(image_bytes)
    return cache_path


def get_diagram_image_base64(
    prompt: str, images_dir: Path, size: tuple[int, int] = (400, 300)
) -> str | None:
    """
    Generate or retrieve a Gemini Flash diagram image as base64-encoded PNG.

    Returns the base64 string, or None if generation fails.
    """
    try:
        path = _generate_diagram_gemini(prompt, size, images_dir)
        return base64.b64encode(path.read_bytes()).decode()
    except Exception as e:
        import traceback

        print(f"[get_diagram_image_base64] ERROR: {e}")
        traceback.print_exc()
        return None
