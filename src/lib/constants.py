"""Project-wide constants for directories, paths, and API models."""

from pathlib import Path

# =============================================================================
# Directory Constants
# =============================================================================

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Font files cache directory (Google Fonts + Font Awesome)
FONTS_DIR = PROJECT_ROOT / "data" / "fonts"

# Jinja2 templates directory for rendering cards
TEMPLATES_DIR = PROJECT_ROOT / "src" / "templates"

# Image cache for generated card illustrations and diagrams
IMAGE_CACHE_DIR = PROJECT_ROOT / "data" / "image_cache"

# Quality test renders directory
QUALITY_TEST_RENDERS_DIR = PROJECT_ROOT / "data" / "quality_test_renders"

# Log file path
LOG_PATH = PROJECT_ROOT / "bb.log"

# =============================================================================
# Model Constants (LLM APIs)
# =============================================================================

# Runware image generation model
RUNWARE_MODEL = "runware:101@1"

# Google Gemini diagram generation model
GEMINI_DIAGRAM_MODEL = "gemini-2.5-flash-image"

# Cerebras LLM for quality control reviews
QUALITY_CONTROL_MODEL = "zai-glm-4.7"
