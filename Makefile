PORT := 9201

run:
	uv run --frozen streamlit run --server.port $(PORT) src/web.py

run-main:
	uv run --frozen python -m main

quality-tests:
	uv run --frozen streamlit run --server.port $(PORT) quality_tests/Home.py

test:
	uv run --frozen pytest tests/
