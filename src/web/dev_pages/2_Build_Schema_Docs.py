"""Dev: build_schema_docs — rendered schema documentation for the agent prompt."""

import streamlit as st

from big_prompt import build_schema_docs
from lib.registry import get_all_schema_classes


def run_streamlit() -> None:
    st.title("Build Schema Docs")
    st.write("Registry → agent prompt schema section")

    classes = get_all_schema_classes()
    st.metric("Schema classes found", len(classes))

    selected = st.radio("Show", ["All"] + [c.__name__ for c in classes])
    if selected != "All":
        classes = [cls for cls in classes if cls.__name__ == selected]

    docs = build_schema_docs(classes)

    md, raw = st.tabs(["Rendered", "Raw"])
    with md:
        st.markdown(docs)
    with raw:
        st.code(docs, language="markdown")


run_streamlit()
