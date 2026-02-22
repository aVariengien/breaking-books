"""Download CSS and font files, cache locally, return rewritten CSS with file:// URLs."""

import hashlib
import logging
import re
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger("bb.lib.font_cache")

ROOT = Path(__file__).resolve().parent.parent.parent
FONTS_DIR = ROOT / "data" / "fonts"
_REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
_FONT_EXTENSIONS = (".woff2", ".woff", ".ttf", ".otf")
_URL_PATTERN = re.compile(r"url\s*\(\s*([^)]+)\s*\)")


def fetch_and_cache_css(css_url: str, cache_prefix: str = "") -> str:
    """
    Fetch CSS from url, download each referenced font file to data/fonts/, return
    CSS with local file:// URLs. Idempotent: re-calling reuses cache.
    """
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    css_cache_dir = FONTS_DIR / "css"
    url_hash = hashlib.sha256(css_url.encode()).hexdigest()[:16]
    css_cache_path = css_cache_dir / f"{cache_prefix}{url_hash}.css"

    if css_cache_path.exists():
        css = css_cache_path.read_text(encoding="utf-8")
    else:
        req = urllib.request.Request(css_url, headers=_REQUEST_HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            css = resp.read().decode("utf-8")
        css_cache_dir.mkdir(exist_ok=True)
        css_cache_path.write_text(css, encoding="utf-8")

    url_to_local: dict[str, str] = {}

    def resolve_and_download(match: re.Match[str]) -> str:
        raw = match.group(1).strip().strip("'\"").strip()
        if not any(raw.lower().endswith(ext) for ext in _FONT_EXTENSIONS):
            return match.group(0)
        abs_url = urllib.parse.urljoin(css_url, raw)
        if abs_url not in url_to_local:
            ext = next(e for e in _FONT_EXTENSIONS if abs_url.lower().endswith(e))
            cache_key = hashlib.sha256(abs_url.encode()).hexdigest()[:16]
            local_path = FONTS_DIR / f"{cache_key}{ext}"
            if not local_path.exists():
                logger.info(f"Downloading font {abs_url} to {local_path}...")
                font_req = urllib.request.Request(abs_url, headers=_REQUEST_HEADERS)
                with urllib.request.urlopen(font_req, timeout=30) as font_resp:
                    local_path.write_bytes(font_resp.read())
            url_to_local[abs_url] = local_path.as_uri()
        return f"url({url_to_local[abs_url]})"

    return _URL_PATTERN.sub(resolve_and_download, css)


def fetch_and_cache_fonts(google_fonts_url: str) -> str:
    """Fetch Google Fonts CSS and fonts, cache locally. Idempotent."""
    return fetch_and_cache_css(google_fonts_url)


def fetch_and_cache_font_awesome() -> str:
    """Fetch Font Awesome CSS and fonts, cache locally. Idempotent."""
    return fetch_and_cache_css(
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.6.0/css/all.min.css",
        cache_prefix="fa-",
    )
