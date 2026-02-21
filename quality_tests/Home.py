"""Quality tests — home page."""

import streamlit as st

st.title("Breaking Books — Quality Tests")
st.markdown(
    """
Use the sidebar to navigate to individual pipeline steps.

| Page | Pipeline step |
|------|---------------|
| Extract Book Content | EPUB → clean HTML |
"""
)
