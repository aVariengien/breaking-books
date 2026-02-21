"""Constants used throughout the application, including those derived from environment variables."""

import os
from pathlib import Path

# Model configuration
MODEL_NAME = os.getenv("BB_MODEL", "gemini/gemini-2.5-flash")
RUNWARE_MODEL = "runware:101@1"
RUNWARE_API_KEY = os.getenv("RUNWARE_API_KEY")

# Image generation configuration
CARD_IMAGE_SIZE = (768, 384)
LANDSCAPE_IMAGE_SIZE = (384, 640)

# Card generation configuration
CONCEPT_CARD_RATIO = 0.7  # 70% concept cards, 30% example cards

# API caching configuration
CACHE_DIR = Path("cache/api_responses")
DISABLE_CACHE = os.getenv("DISABLE_API_CACHE", "false").lower() == "true"

# EPUB processing configuration
LUA_FILTER_FILENAME = "remove_footnotes.lua"

# Template configuration
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
CARD_TEMPLATE_FILENAME = "card_template.html"
SECTION_TEMPLATE_FILENAME = "section_card_template.html"
TOC_TEMPLATE_FILENAME = "toc_template.html"
KEY_PASSAGES_TEMPLATE_FILENAME = "key_passages_template.html"

# PDF page sizes in points (1 point = 1/72 inch)
# A4 Portrait: 210mm x 297mm
A4_PORTRAIT_WIDTH = 595.276
A4_PORTRAIT_HEIGHT = 841.890

# A4 Landscape: 297mm x 210mm
A4_LANDSCAPE_WIDTH = 841.890
A4_LANDSCAPE_HEIGHT = 595.276

# A5 Landscape: 210mm x 148mm
A5_LANDSCAPE_WIDTH = 595.276  # Standard A5 landscape width (210mm)
A5_LANDSCAPE_HEIGHT = 419.528  # Standard A5 landscape height (148mm)

# A6 Landscape: 148mm x 105mm
A6_LANDSCAPE_WIDTH = 419.528
A6_LANDSCAPE_HEIGHT = 297.638

# PDF processing configuration
SIZE_TOLERANCE = 5.0  # points
