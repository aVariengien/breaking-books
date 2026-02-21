# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Breaking Books is a Python application that converts ebooks (EPUB format) into visual learning cards and printable PDFs. The system uses AI to analyze book content, extract key concepts, generate illustrations, and create printable card decks for physical study aids.

## Core Architecture

The pipeline follows this sequence:
1. **EPUB Processing** (`clean_epub.py`) - Convert EPUB to clean HTML with normalized image paths
2. **Book Analysis** (`book_to_cards.py`) - Use AI to analyze structure, extract sections, chapters, and key passages
3. **Card Generation** (`book_to_cards.py`) - Generate concept and example cards with AI-created illustrations
4. **Card Processing** (`process_cards.py`) - Convert cards to HTML/PDF using Jinja2 templates
5. **PDF Combination** (`pdf_combiner.py`) - Combine individual cards into printable sheets

### Key Components

- **API Caching** (`api_cache.py`) - Caches AI API calls to avoid expensive re-requests. Uses content hashing for deterministic caching.
- **Templates** (`templates/`) - Jinja2 templates for card layouts, sections, and table of contents
- **Prompts** (`prompts/card_creation.py`) - AI prompts for book analysis and card generation
- **Web Interface** (`app.py`, `web.py`) - Streamlit app for viewing generated cards

### Data Models

The system uses Pydantic models extensively:
- `BookStructure` - Overall book analysis with sections, chapters, key passages
- `CardSet` - Collection of generated cards with metadata
- `CardDefinition` - Individual card with title, description, illustration, quotes, and base64 image
- `Section` - Book section with color coding and landscape descriptions

## Development Commands

### Setup and Dependencies
```bash
# Install dependencies (uses uv for package management)
uv sync

# Install development dependencies
uv sync --group dev
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_book_to_cards.py

# Run with verbose output
pytest -v
```

### Code Quality
```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint code
ruff check src/ tests/
```

### Running the Application
```bash
# Generate cards from EPUB (main CLI)
python src/main.py data/book.epub

# Start web viewer
streamlit run app.py

# Convert EPUB to HTML only
python -m src.clean_epub input.epub

# Process existing JSONL cards to PDF
python -m src.process_cards cards.jsonl
```

## API Configuration

The system uses multiple AI services:
- **LLM**: Gemini 2.5 Flash (`gemini/gemini-2.5-flash-preview-05-20`) for text analysis and card generation
- **Image Generation**: Runware API (`runware:101@1`) for card illustrations
- **Caching**: File-based caching in `cache/api_responses/` with content-based hashing

Environment variables:
- `DISABLE_API_CACHE=true` - Disable API response caching
- API keys configured through litellm for various providers

## File Organization

- `src/` - Main source code
- `tests/` - Test files with fixtures
- `data/` - Sample books and generated outputs
- `cache/` - API response cache (gitignored)
- `templates/` - HTML templates for card rendering

## Key Design Patterns

1. **Deterministic Processing** - EPUB processing is deterministic regardless of file paths to enable reliable caching
2. **Async/Parallel Processing** - Image generation and API calls use asyncio and joblib for performance
3. **Template-Based Rendering** - All visual output uses Jinja2 templates for consistency
4. **Comprehensive Caching** - AI API calls are cached with content hashing to avoid expensive re-requests
5. **Type Safety** - Extensive use of Pydantic models and type hints throughout

## Testing Strategy

Tests focus on three main functions:
- `analyze_book_structure()` - Validates book analysis output
- `generate_cards_from_sections()` - Tests card generation logic
- `generate_images_for_game()` - Verifies image generation integration

Test fixtures include sample EPUB files and expected HTML outputs for deterministic testing.