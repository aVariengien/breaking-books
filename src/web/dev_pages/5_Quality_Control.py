"""Dev: quality_control — cards.json → QC report.

CLI:  python src/web/dev_pages/5_Quality_Control.py [cards.json]
      (picks a random JSON from data/ when no argument is given)
"""

import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(ROOT / "src"))

from lib.models import Config, OutDir, WorkDir  # noqa: E402
from lib.streamlit_utils import in_streamlit  # noqa: E402
from tools.quality_control import quality_control  # noqa: E402

DATA_DIR = ROOT / "data"


def _json_files() -> list[Path]:
    return sorted(DATA_DIR.glob("*.json"))


def run_qc(cards_json_path: Path) -> str:
    config = Config(num_cards=15)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        work_dir = WorkDir.create(tmp_path / "tmp")
        out_dir = OutDir.create(tmp_path / "out")
        return quality_control(cards_json_path, config, work_dir, out_dir)


def run_cli() -> None:
    json_files = _json_files()
    if not json_files:
        sys.exit(f"No JSON files found in {DATA_DIR}")

    if len(sys.argv) > 1:
        cards_json_path = Path(sys.argv[1])
    else:
        cards_json_path = random.choice(json_files)
        print(f"Picked: {cards_json_path.name}", file=sys.stderr)

    report = run_qc(cards_json_path)
    print(report)


def run_streamlit() -> None:
    import streamlit as st

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


if in_streamlit():
    run_streamlit()
else:
    run_cli()
