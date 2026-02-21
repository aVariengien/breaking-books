PORT := 9201

run:
	uv run --frozen streamlit run --server.port $(PORT) src/web.py

run-main:
	uv run --frozen python -m main

test:
	uv run --frozen pytest tests/
