# ---- build stage: install Python deps with uv ----
FROM python:3.12 AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

# ---- runtime stage ----
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

# System libs required by WeasyPrint / Pango / Cairo
RUN apt-get update && apt-get install -y --no-install-recommends \
      libcairo2 \
      libgdk-pixbuf-2.0-0 \
      libglib2.0-0 \
      libpango-1.0-0 \
      libpangoft2-1.0-0 \
      libpangocairo-1.0-0 \
      libharfbuzz-subset0 \
      pandoc && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv .venv/

COPY src ./src

# data/ holds only runtime caches (fonts, generated images) and output/ holds the
# generated decks. Both are bind-mounted at runtime — create the mount points so
# the image never bakes in the local 200MB EPUB library.
RUN mkdir -p /app/data/fonts /app/data/image_cache /app/output

EXPOSE 9201

CMD ["/app/.venv/bin/streamlit", "run", "src/web/app.py", \
     "--server.port=9201", "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.fileWatcherType=none", \
     "--browser.gatherUsageStats=false"]
