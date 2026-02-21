"""Quality tests — home page."""

import streamlit as st

st.title("Breaking Books — Quality Tests")
st.markdown(
    """
Use the sidebar to navigate to individual pipeline steps.

| Page | Pipeline step |
|------|---------------|
| Extract Book Content | EPUB / HTML / MD → clean HTML |
| Render Templates | Card dict + Jinja2 → PDF → PNG (one card per schema type × template) |
| PDF to PNGs | PDF → PNG conversion used by QC visual review |
| Merge PDFs | Card PDFs → printable A4 sheet (2-up / 4-up) |
"""
)
