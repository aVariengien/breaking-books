"""Dev: quality_control — cards.json → QC report."""

import tempfile
from pathlib import Path

import streamlit as st

from lib.models import Config, OutDir, WorkDir
from tools.quality_control import quality_control

DATA_DIR = Path(__file__).parents[3] / "data"


def _json_files() -> list[Path]:
    return sorted(DATA_DIR.glob("*.json"))


def run_qc(cards_json_path: Path) -> str:
    config = Config(num_cards=15)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        work_dir = WorkDir.create(tmp_path / "tmp")
        out_dir = OutDir.create(tmp_path / "out")
        return quality_control(cards_json_path, config, work_dir, out_dir)


def run_streamlit() -> None:
    st.title("Quality Control")
    st.caption("Pipeline step 3: cards.json → QC report")

    json_files = _json_files()
    if not json_files:
        st.error(f"No JSON files found in {DATA_DIR}")
        st.stop()

    selected = st.selectbox("cards.json", json_files, format_func=lambda p: p.name)

    with st.spinner("Running quality control…"):
        report = run_qc(selected)

    st.markdown(report)


run_streamlit()
