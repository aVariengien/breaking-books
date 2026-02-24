"""Breaking Books — Streamlit entrypoint.

Run in prod mode:  streamlit run src/web/app.py
Run in dev mode:   BB_DEV=1 streamlit run src/web/app.py  (adds dev pages)
"""

import os

import streamlit as st

st.set_page_config(page_title="Breaking Books", layout="wide")

prod_pages = [
    st.Page("prod_pages/1_Generator.py", title="Generator", icon="📚"),
    st.Page("prod_pages/2_Render_Deck.py", title="Render Deck", icon="🃏"),
]

dev_pages = [
    st.Page("dev_pages/1_Extract.py", title="Extract Book Content", icon="🔍"),
    st.Page("dev_pages/2_Build_Schema_Docs.py", title="Build Schema Docs", icon="📄"),
    st.Page("dev_pages/2_Render_Templates.py", title="Render Templates", icon="🎨"),
    st.Page("dev_pages/3_PDF_to_PNGs.py", title="PDF to PNGs", icon="🖼️"),
    st.Page("dev_pages/4_Merge_PDFs.py", title="Merge PDFs", icon="📎"),
    st.Page("dev_pages/5_Quality_Control.py", title="Quality Control", icon="✅"),
    st.Page("dev_pages/6_Card_Generator.py", title="Card Generator", icon="⚡"),
    st.Page("dev_pages/7_Agent_Log.py", title="Agent Log Viewer", icon="📋"),
]

pages = prod_pages + (dev_pages if os.environ.get("BB_DEV") else [])
st.navigation(pages).run()
