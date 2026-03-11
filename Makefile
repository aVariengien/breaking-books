PORT := 9201

dev:
	PYTHONPATH=src BB_DEV=1 DYLD_LIBRARY_PATH=/opt/homebrew/lib uv run --frozen streamlit run --server.port $(PORT) src/web/app.py

run:
	PYTHONPATH=src DYLD_LIBRARY_PATH=/opt/homebrew/lib uv run --frozen streamlit run --server.port $(PORT) src/web/app.py

run-main:
	uv run --frozen python -m main

check:
	uv run --frozen ty check
	uv run --frozen ruff check

test: check
	uv run --frozen pytest tests/

font-metadata:
	uv run --frozen python scripts/generate_font_metadata.py
