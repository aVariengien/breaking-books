"""Download Google Fonts CSS and font files, cache locally, return rewritten CSS."""

import hashlib
import logging
import re
import urllib.request
from pathlib import Path

logger = logging.getLogger("bb.lib.font_cache")

# Global font cache: data/fonts/ at project root
ROOT = Path(__file__).resolve().parent.parent.parent
FONTS_DIR = ROOT / "data" / "fonts"

# User-Agent for font requests
_REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

# Font extensions we cache (WeasyPrint supports all of these)
_FONT_EXTENSIONS = (".woff2", ".woff", ".ttf", ".otf")


def fetch_and_cache_fonts(google_fonts_url: str) -> str:
    """
    Fetch Google Fonts CSS, download each font file (.woff2, .woff, .ttf, .otf)
    to data/fonts/, return CSS with local file:// URLs.

    Caches both the CSS response and font files. Idempotent: re-calling with same
    URL reuses cached files without hitting Google.
    """
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    css_cache_dir = FONTS_DIR / "css"
    url_hash = hashlib.sha256(google_fonts_url.encode()).hexdigest()[:16]
    css_cache_path = css_cache_dir / f"{url_hash}.css"

    if css_cache_path.exists():
        css = css_cache_path.read_text(encoding="utf-8")
    else:
        req = urllib.request.Request(google_fonts_url, headers=_REQUEST_HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            css = resp.read().decode("utf-8")
        css_cache_dir.mkdir(exist_ok=True)
        css_cache_path.write_text(css, encoding="utf-8")

    # Match url(...) in src: declarations; Google Fonts uses unquoted URLs
    url_pattern = re.compile(r"url\s*\(\s*([^)]+)\s*\)")
    urls = []
    for m in url_pattern.finditer(css):
        raw = m.group(1).strip().strip("'\"").strip()
        if any(raw.lower().endswith(ext) for ext in _FONT_EXTENSIONS):
            urls.append(raw)

    url_to_local: dict[str, str] = {}
    for url in set(urls):
        ext = next(e for e in _FONT_EXTENSIONS if url.lower().endswith(e))
        cache_key = hashlib.sha256(url.encode()).hexdigest()[:16]
        local_path = FONTS_DIR / f"{cache_key}{ext}"
        if not local_path.exists():
            logger.info(f"Downloading font {url} to {local_path}...")
            font_req = urllib.request.Request(url, headers=_REQUEST_HEADERS)
            with urllib.request.urlopen(font_req, timeout=30) as font_resp:
                local_path.write_bytes(font_resp.read())
        url_to_local[url] = local_path.as_uri()

    rewritten = css
    for url, local_uri in url_to_local.items():
        rewritten = rewritten.replace(f"url({url})", f"url({local_uri})")
    return rewritten
