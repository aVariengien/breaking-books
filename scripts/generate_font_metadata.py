#!/usr/bin/env python3
"""
Generate src/lib/font_metadata.py from the Google Fonts API.

Reads the curated font list from src/big_prompt.py, queries the Google Fonts
API v2 for each font, and writes a FONT_SPECS dict mapping font name to its
correct Google Fonts CSS2 family parameter string.

Usage:
    GOOGLE_FONTS_API_KEY=your_key uv run --frozen python scripts/generate_font_metadata.py
    uv run --frozen python scripts/generate_font_metadata.py --key your_key

Get a free API key at: https://developers.google.com/fonts/docs/developer_api
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
OUTPUT_FILE = SRC / "lib" / "font_metadata.py"
GF_API_URL = "https://www.googleapis.com/webfonts/v1/webfonts"

sys.path.insert(0, str(SRC))
from big_prompt import PROMPT  # noqa: E402


def extract_font_names() -> list[str]:
    """Parse font names from the typography section of the agent prompt.

    Matches lines like: - **Font Name** — ...
    Excludes design-principle bullets (those are longer phrases).
    """
    fonts = []
    for match in re.finditer(r"^- \*\*([A-Z][^*]+)\*\*", PROMPT, re.MULTILINE):
        name = match.group(1).strip()
        # Skip non-font bullets (design principles start with capital but are sentences)
        if len(name.split()) <= 4 and not name.endswith("."):
            fonts.append(name)
    return sorted(set(fonts))


def fetch_font_metadata(font_name: str, api_key: str) -> dict | None:
    """Query the Google Fonts API v2 for a single font family."""
    params = urllib.parse.urlencode({"family": font_name, "key": api_key})
    url = f"{GF_API_URL}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            items = data.get("items", [])
            return items[0] if items else None
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for {font_name!r}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Error fetching {font_name!r}: {e}", file=sys.stderr)
        return None


def build_family_param(font_name: str, meta: dict) -> str:
    """
    Build the Google Fonts CSS2 `family=` parameter string from API metadata.

    For variable fonts (have a wght axis): use range syntax.
    For static fonts: enumerate all available weight+style combinations.
    """
    family = font_name.replace(" ", "+")
    axes = meta.get("axes", [])
    variants: list[str] = meta.get("variants", ["regular"])

    # Parse available upright weights and italic weights from variants list
    upright_weights: list[int] = []
    italic_weights: list[int] = []
    for v in variants:
        if v == "regular":
            upright_weights.append(400)
        elif v == "italic":
            italic_weights.append(400)
        elif v.endswith("italic"):
            w = int(v.replace("italic", ""))
            italic_weights.append(w)
        else:
            upright_weights.append(int(v))

    upright_weights = sorted(set(upright_weights))
    italic_weights = sorted(set(italic_weights))
    has_italic = bool(italic_weights)

    # Check for variable weight axis
    wght_axis = next((a for a in axes if a.get("tag") == "wght"), None)

    if wght_axis:
        w_min = int(wght_axis["start"])
        w_max = int(wght_axis["end"])
        if has_italic:
            return f"{family}:ital,wght@0,{w_min}..{w_max};1,{w_min}..{w_max}"
        else:
            return f"{family}:wght@{w_min}..{w_max}"
    else:
        # Static font — enumerate all weights explicitly
        if not has_italic:
            weights_str = ";".join(str(w) for w in upright_weights)
            return f"{family}:wght@{weights_str}"

        all_weights = sorted(set(upright_weights) | set(italic_weights))
        specs = []
        for w in all_weights:
            if w in upright_weights:
                specs.append(f"0,{w}")
            if w in italic_weights:
                specs.append(f"1,{w}")
        return f"{family}:ital,wght@{';'.join(specs)}"


def write_output(font_specs: dict[str, str], failed: list[str]) -> None:
    """Write the generated font_metadata.py file."""
    lines = [
        '"""',
        "Google Fonts family parameter strings for the curated font index.",
        "",
        "AUTO-GENERATED — do not edit by hand.",
        "Regenerate with: uv run --frozen python scripts/generate_font_metadata.py",
        '"""',
        "",
        "# Maps font family name → Google Fonts CSS2 `family=` parameter string.",
        "# Used by build_google_fonts_url() in src/tools/render_template.py.",
        "FONT_SPECS: dict[str, str] = {",
    ]
    for name, spec in sorted(font_specs.items()):
        lines.append(f"    {name!r}: {spec!r},")
    lines.append("}")
    lines.append("")

    if failed:
        lines.append("# Fonts not found in the Google Fonts API (may need name correction):")
        for name in sorted(failed):
            lines.append(f"# - {name!r}")
        lines.append("")

    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {OUTPUT_FILE} ({len(font_specs)} fonts, {len(failed)} failed)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--key",
        default=os.environ.get("GOOGLE_FONTS_API_KEY", ""),
        help="Google Fonts API key (or set GOOGLE_FONTS_API_KEY env var)",
    )
    args = parser.parse_args()

    if not args.key:
        print(
            "Error: Google Fonts API key required.\n"
            "Set GOOGLE_FONTS_API_KEY env var or pass --key.",
            file=sys.stderr,
        )
        sys.exit(1)

    fonts = extract_font_names()
    print(f"Found {len(fonts)} fonts in prompt. Querying Google Fonts API...")

    font_specs: dict[str, str] = {}
    failed: list[str] = []

    for i, name in enumerate(fonts, 1):
        print(f"  [{i}/{len(fonts)}] {name}", end=" ... ", flush=True)
        meta = fetch_font_metadata(name, args.key)
        if meta:
            spec = build_family_param(name, meta)
            font_specs[name] = spec
            print(spec)
        else:
            failed.append(name)
            print("FAILED")

    write_output(font_specs, failed)

    if failed:
        print(f"\nWarning: {len(failed)} fonts failed. Check names against Google Fonts.")
        for name in sorted(failed):
            print(f"  - {name}")


if __name__ == "__main__":
    main()
