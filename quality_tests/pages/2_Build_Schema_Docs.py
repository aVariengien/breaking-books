"""Quality test: build_schema_docs — rendered schema documentation for the agent prompt.

CLI:       python quality_tests/pages/2_Build_Schema_Docs.py
Streamlit: run via `make quality-tests` and open this page in the sidebar.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from lib.registry import build_schema_docs, get_all_schema_classes  # noqa: E402
from lib.streamlit_utils import in_streamlit  # noqa: E402


def run_cli() -> None:
    classes = get_all_schema_classes()
    print(f"Found {len(classes)} schema class(es): {[c.__name__ for c in classes]}\n")
    print(build_schema_docs())


def run_streamlit() -> None:
    import streamlit as st

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


if in_streamlit():
    run_streamlit()
else:
    run_cli()
