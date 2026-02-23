"""Dev: build_schema_docs — rendered schema documentation for the agent prompt."""

import streamlit as st

from big_prompt import build_schema_docs
from lib.registry import get_all_schema_classes


def run_streamlit() -> None:
    st.title("Build Schema Docs")
    st.caption("Registry → agent prompt schema section")

    classes = get_all_schema_classes()
    st.metric("Schema classes found", len(classes))
    st.write([c.__name__ for c in classes])

    docs = build_schema_docs()

    st.subheader("Rendered (as seen by the agent)")
    st.markdown(docs)

    st.subheader("Raw text")
    st.code(docs, language="markdown")

    st.metric("Total characters", f"{len(docs):,}")


run_streamlit()
