"""
Caching layer for AI API calls to avoid repeated expensive requests.

Set DISABLE_API_CACHE=true to disable caching entirely.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict

import aiohttp
from litellm import (
    ModelResponse,
)
from litellm import acompletion as _litellm_acompletion
from litellm import completion as _litellm_completion
from runware import IImageInference, Runware

# Configuration
CACHE_DIR = Path("cache/api_responses")
DISABLE_CACHE = os.getenv("DISABLE_API_CACHE", "false").lower() == "true"


def _ensure_cache_dir():
    """Ensure cache directory exists."""
    if not DISABLE_CACHE:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _hash_request(func_name: str, *args, **kwargs) -> str:
    """Create deterministic hash of API request."""
    request_data = {"function": func_name, "args": args, "kwargs": kwargs}
    request_str = json.dumps(request_data, sort_keys=True, default=str)
    return hashlib.sha256(request_str.encode()).hexdigest()[:16]


def _load_cached_response(cache_file: Path) -> Dict[str, Any] | None:
    """Load cached response if it exists."""
    if cache_file.exists() and not DISABLE_CACHE:
        try:
            return json.loads(cache_file.read_text())
        except (json.JSONDecodeError, OSError):
            # If cache file is corrupted, ignore it
            return None
    return None


def _save_cached_response(cache_file: Path, response_data: Dict[str, Any]):
    """Save response to cache."""
    if not DISABLE_CACHE:
        _ensure_cache_dir()
        try:
            cache_file.write_text(json.dumps(response_data, indent=2, default=str))
        except OSError:
            # If we can't write to cache, just continue without caching
            pass


def completion(*args, **kwargs):
    """Cached version of litellm.completion."""
    cache_key = _hash_request("completion", *args, **kwargs)
    cache_file = CACHE_DIR / f"completion_{cache_key}.json"

    # Try to load from cache
    cached_data = _load_cached_response(cache_file)
    if cached_data is not None:
        print("🔄 Using cached completion response")
        return ModelResponse.model_validate(cached_data["output"])

    # Make real API call
    print("🌐 Making fresh completion API call")
    response = _litellm_completion(*args, **kwargs)

    # Cache the response
    cache_data = {"args": args, "kwargs": kwargs, "output": response.model_dump()}
    _save_cached_response(cache_file, cache_data)

    return response


async def acompletion(*args, **kwargs):
    """Cached version of litellm.acompletion."""
    cache_key = _hash_request("acompletion", *args, **kwargs)
    cache_file = CACHE_DIR / f"acompletion_{cache_key}.json"

    # Try to load from cache
    cached_data = _load_cached_response(cache_file)
    if cached_data is not None:
        print("🔄 Using cached acompletion response")
        return ModelResponse.model_validate(cached_data["output"])

    # Make real API call
    print("🌐 Making fresh acompletion API call")
    response = await _litellm_acompletion(*args, **kwargs)

    # Cache the response
    cache_data = {"args": args, "kwargs": kwargs, "output": response.model_dump()}
    _save_cached_response(cache_file, cache_data)

    return response


async def generate_single_image_async(
    prompt: str, image_size: tuple[int, int], runware_model: str
) -> str:
    """Cached version of image generation."""

    # Create cache key from request parameters
    cache_key = _hash_request("generate_image", prompt, image_size, runware_model)
    cache_file = CACHE_DIR / f"image_{cache_key}.json"

    # Try to load from cache
    cached_data = _load_cached_response(cache_file)
    if cached_data is not None:
        return cached_data["output"]

    # Make real API call
    runware = Runware(api_key=os.getenv("RUNWARE_API_KEY"))
    await runware.connect()

    request_image = IImageInference(
        positivePrompt=prompt,
        model=runware_model,
        numberResults=1,
        negativePrompt="Text, label, diagram, blurry, low quality, distorted",
        height=image_size[0],
        width=image_size[1],
    )

    images = await runware.imageInference(requestImage=request_image)

    if images:
        async with aiohttp.ClientSession() as session:
            async with session.get(images[0].imageURL) as response:
                if response.status == 200:
                    content = await response.read()
                    image_base64 = base64.b64encode(content).decode("utf-8")

                    # Cache the response
                    cache_data = {
                        "args": (prompt, image_size, runware_model),
                        "kwargs": {},
                        "output": image_base64,
                    }
                    _save_cached_response(cache_file, cache_data)

                    return image_base64

    return "No image generated"


def get_cache_stats() -> Dict[str, int]:
    """Get statistics about cached responses."""
    if DISABLE_CACHE or not CACHE_DIR.exists():
        return {"total_cached": 0, "completions": 0, "images": 0}

    completion_files = len(list(CACHE_DIR.glob("completion_*.json")))
    acompletion_files = len(list(CACHE_DIR.glob("acompletion_*.json")))
    image_files = len(list(CACHE_DIR.glob("image_*.json")))

    return {
        "total_cached": completion_files + acompletion_files + image_files,
        "completions": completion_files + acompletion_files,
        "images": image_files,
    }


def clear_cache():
    """Clear all cached responses."""
    if CACHE_DIR.exists():
        for cache_file in CACHE_DIR.glob("*.json"):
            cache_file.unlink()
        print("🧹 Cleared API cache")
    else:
        print("🧹 No cache to clear")
