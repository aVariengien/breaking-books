# Breaking Books

A Python project with modern development practices.

## Features

- Modern Python packaging with `pyproject.toml`
- Fast dependency management with `uv`
- Code quality tools:
  - Black for code formatting
  - isort for import sorting
  - Ruff for fast linting
  - MyPy for static type checking
- Pre-commit hooks for automated code quality checks
- Pytest for testing

## Setup

1. Install `uv` (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Create and activate a virtual environment:
```bash
uv venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
uv pip install -e ".[dev]"
```

4. Install pre-commit hooks:
```bash
pre-commit install
```

## Development

- Run tests: `pytest`
- Format code: `black .`
- Sort imports: `isort .`
- Type checking: `mypy .`
- Lint code: `ruff check .`

## Project Structure

```
breaking-books/
├── src/
│   └── breaking_books/
│       └── __init__.py
├── tests/
│   └── __init__.py
├── pyproject.toml
├── .pre-commit-config.yaml
└── README.md
```

## License

MIT
