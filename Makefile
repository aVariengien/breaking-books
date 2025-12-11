PORT := 9201

run:
	uv run --frozen streamlit run --server.port $(PORT) src/simple_web.py
