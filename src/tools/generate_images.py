"""Generate card images via Runware, with a file cache keyed by prompt hash."""

from pathlib import Path


def generate_image(prompt: str, size: tuple[int, int], cache_dir: Path) -> Path:
    """
    Generate a single image from a text prompt.

    Uses a file cache: if `cache_dir/{sha256(prompt)}.png` exists, return it directly.
    Otherwise calls the Runware API and saves the result.

    Returns the path to the cached PNG file.
    """
    raise NotImplementedError()


def generate_images_for_cards(cards_json_path: Path, images_dir: Path) -> None:
    """
    Generate and cache images for every card in cards.json that lacks one.

    Reads `image_description` from each card, calls `generate_image`, and writes
    the resulting path back into cards.json under `image_path`.
    """
    raise NotImplementedError()
