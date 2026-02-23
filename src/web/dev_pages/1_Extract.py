"""Dev: extract_book_content — EPUB → clean HTML.

CLI:  python src/web/dev_pages/1_Extract.py [epub]
      (picks a random EPUB from data/ when no argument is given)
"""

import random
import sys
from pathlib import Path

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "src"))

from lib.streamlit_utils import in_streamlit  # noqa: E402
from tools.extract_book_content import extract_book_content  # noqa: E402

DATA_DIR = ROOT / "data"


def _epubs() -> list[Path]:
    return sorted(DATA_DIR.glob("*.epub"))


def run_cli() -> None:
    epubs = _epubs()
    if not epubs:
        sys.exit(f"No EPUB files found in {DATA_DIR}")

    if len(sys.argv) > 1:
        epub = Path(sys.argv[1])
    else:
        epub = random.choice(epubs)
        print(f"Picked: {epub.name}", file=sys.stderr)

    print(extract_book_content(epub))


def run_streamlit() -> None:
    import streamlit as st

    st.title("Extract Book Content")
    st.caption("Pipeline step 1: EPUB → clean HTML")

    epubs = _epubs()
    if not epubs:
        st.error(f"No EPUB files found in {DATA_DIR}")
        st.stop()

    selected = st.selectbox("EPUB", epubs, format_func=lambda p: p.name)

    with st.spinner("Converting…"):
        html = extract_book_content(selected)

    lines = html.splitlines()
    longest_lineno = max(range(len(lines)), key=lambda i: len(lines[i]))
    longest_line = lines[longest_lineno]

    st.metric("Total characters", f"{len(html):,}")
    st.markdown(f"**Longest line:** line {longest_lineno + 1} ({len(longest_line):,} chars)")
    st.code(longest_line, language="html")

    st.subheader("Full HTML")
    st.code(html, language="html")


if in_streamlit():
    run_streamlit()
else:
    run_cli()
