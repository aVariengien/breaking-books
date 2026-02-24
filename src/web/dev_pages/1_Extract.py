"""Dev: extract_book_content — EPUB → clean HTML."""

from pathlib import Path

import streamlit as st

from lib.constants import PROJECT_ROOT
from tools.extract_book_content import extract_book_content

DATA_DIR = PROJECT_ROOT / "data"


def _epubs() -> list[Path]:
    return sorted(DATA_DIR.glob("*.epub"))


def run_streamlit() -> None:
    st.title("Extract Book Content")
    st.write(
        f"Extract book content from an EPUB file. Select any EPUB from `{DATA_DIR.resolve()}`."
    )

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


run_streamlit()
