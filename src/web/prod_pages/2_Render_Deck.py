"""Render a full deck from a cards.json file.

Upload a cards.json, pick card size, render all cards to a merged PDF,
preview inline, and download PDF or a ZIP of individual card PNGs.
"""

import streamlit as st

from web.utils import render_deck_ui

st.title("Render Deck")
st.caption("Upload a cards.json → pick card size → render → preview & download")

uploaded = st.file_uploader(
    "cards.json",
    type=["json"],
    key="deck_uploader",
    label_visibility="collapsed",
)

if uploaded is not None:
    render_deck_ui(uploaded.read(), key_prefix="deck")
else:
    st.info("Upload a `cards.json` to get started.")
