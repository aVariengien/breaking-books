FROM python:3.12 AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Install uv and sync dependencies (system libs are installed in the runtime stage)
RUN pip install uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app
# Runtime system deps for pandoc + WeasyPrint/Pango/GTK stack (libgobject-2.0)
RUN apt-get update && apt-get install -y --no-install-recommends \
      pandoc \
      libcairo2 \
      libgdk-pixbuf-2.0-0 \
      libglib2.0-0 \
      libpango-1.0-0 \
      libpangoft2-1.0-0 \
      libpangocairo-1.0-0 \
      libharfbuzz-subset0 && \
    rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/.venv .venv/
COPY src ./src
CMD ["/app/.venv/bin/streamlit", "run", "src/simple_web.py"]
