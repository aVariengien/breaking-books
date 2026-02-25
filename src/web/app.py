"""Breaking Books — Streamlit entrypoint.

Run in prod mode:  streamlit run src/web/app.py
Run in dev mode:   BB_DEV=1 streamlit run src/web/app.py  (adds dev pages)
"""

import os

import streamlit as st
from lib import log

if "log_setup" not in st.session_state:
    log.setup()
    st.session_state["log_setup"] = True

IS_DEV = os.environ.get("BB_DEV")

st.set_page_config(page_title="Breaking Books", layout="wide")

prod_pages = [
    st.Page("prod_pages/1_Generator.py", title="Generator", icon="📚"),
    st.Page("prod_pages/2_Render_Deck.py", title="Render Deck", icon="🖨️"),
]

dev_pages = [
    st.Page("dev_pages/2_Build_Schema_Docs.py", title="Schemas", icon="📄"),
    st.Page("dev_pages/2_Render_Templates.py", title="Templates", icon="🎨"),
    st.Page("dev_pages/1_Extract.py", title="EPUB → Text", icon="✂️"),
    st.Page("dev_pages/4_Merge_PDFs.py", title="Merge PDFs", icon="📎"),
    st.Page("dev_pages/5_Quality_Control.py", title="Quality Control", icon="✅"),
    st.Page("dev_pages/7_Agent_Log.py", title="Agent Log Viewer", icon="📋"),
    st.Page("dev_pages/6_Card_Generator.py", title="Fast Generator", icon="⚡"),
]


if IS_DEV:
    pages = {
        "Prod": prod_pages,
        "Dev": dev_pages,
    }
else:
    pages = prod_pages

st.navigation(pages).run()
