import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, ClassVar

import streamlit as st
from ai_transforms import create_book_structure
from pydantic import BaseModel

from clean_epub import epub_to_clean_html
from pdf_combiner import combine
from process_cards import generate_cards, generate_section_cards, generate_toc


class Asset(BaseModel):
    name: str
    type: str
    multiple: bool = False

    class Config:
        frozen = True

    def prompt(self, key: str) -> Path:
        return st.file_uploader(
            self.name, type=self.type, accept_multiple_files=self.multiple, key=key
        )


class Assets:
    EPUB = Asset(name="EPUB", type="epub")
    CLEAN_HTML = Asset(name="Clean HTML", type="html")
    COMBINED_PDF = Asset(name="✨ Combined PDF", type="pdf")
    PDF_DIR = Asset(name="PDF directory", type="pdf", multiple=True)
    CARDS_JSONL = Asset(name="Cards JSONL", type="jsonl")
    STRUCTURE_JSON = Asset(name="Structure JSON", type="json")
    TOC_PDF = Asset(name="Table of Contents PDF", type="pdf")
    TOC_HTML = Asset(name="Table of Contents HTML", type="html")


class Step:
    name: ClassVar[str] = "Step"

    def configure(self) -> bool:
        return True

    def list_inputs(self) -> list[Assets]:
        raise NotImplementedError

    def list_outputs(self) -> list[Assets]:
        raise NotImplementedError

    def run(self, inputs) -> dict[Assets, Any]:
        raise NotImplementedError


class CombinePdfStep(Step):
    name = "Combine all PDFs in one"

    def __init__(self) -> None:
        self.cards_a6 = False
        self.pages_a5 = False

    def configure(self):
        self.cards_a6 = st.checkbox("Make cards A6 instead of A5", self.cards_a6, key="cards_a6")
        self.pages_a5 = st.checkbox("Make pages A5 instead of A4", self.pages_a5, key="pages_a5")

    def list_inputs(self) -> list[Assets]:
        return [Assets.PDF_DIR]

    def list_outputs(self) -> list[Assets]:
        return [Assets.COMBINED_PDF]

    def run(self, inputs):
        dir = inputs[Assets.PDF_DIR]
        combined_pdf = combine(
            dir, dir / "combined.pdf", four_up=self.cards_a6, scale_a4=self.pages_a5
        )
        return {Assets.COMBINED_PDF: combined_pdf}


class GenerateCardPdfsStep(Step):
    name = "Generate PDFs for each card"

    def __init__(self) -> None:
        self.n_jobs = os.cpu_count()

    # def configure(self):
    #     self.n_jobs = st.number_input(
    #         "Number of parallel jobs",
    #         min_value=1,
    #         max_value=os.cpu_count(),
    #         value=self.n_jobs,
    #         key="generate_cards_pdfs.n_jobs",
    #     )

    def list_inputs(self) -> list[Assets]:
        return [Assets.CARDS_JSONL]

    def list_outputs(self) -> list[Assets]:
        return [Assets.PDF_DIR]

    def run(self, inputs):
        output_dir = generate_cards(inputs[Assets.CARDS_JSONL], n_jobs=self.n_jobs)
        return {Assets.PDF_DIR: output_dir}


class GenerateTocPdfStep(Step):
    name = "Generate fancy Table of Contents"

    def list_inputs(self) -> list[Assets]:
        return [Assets.STRUCTURE_JSON]

    def list_outputs(self) -> list[Assets]:
        return [Assets.TOC_PDF, Assets.PDF_DIR]

    def run(self, inputs):
        toc_pdf = generate_toc(inputs[Assets.STRUCTURE_JSON])
        return {Assets.TOC_PDF: toc_pdf, Assets.TOC_HTML: toc_pdf.with_suffix(".html")}


class GenerateSectionCardsPdfStep(Step):
    name = "Generate section cards"

    def __init__(self) -> None:
        self.n_jobs = os.cpu_count()

    def list_inputs(self) -> list[Assets]:
        return [Assets.STRUCTURE_JSON]

    def list_outputs(self) -> list[Assets]:
        return [Assets.PDF_DIR]

    def run(self, inputs):
        output_dir = generate_section_cards(inputs[Assets.STRUCTURE_JSON], n_jobs=self.n_jobs)
        return {Assets.PDF_DIR: output_dir}


class CleanEpubStep(Step):
    name = "Clean EPUB"

    def list_inputs(self) -> list[Assets]:
        return [Assets.EPUB]

    def list_outputs(self) -> list[Assets]:
        return [Assets.CLEAN_HTML]

    def run(self, inputs):
        epub = inputs[Assets.EPUB]
        clean_html = epub_to_clean_html(epub, None, None)
        return {Assets.CLEAN_HTML: clean_html}


class CreateBookStructureStep(Step):
    name = "Create book structure"

    def list_inputs(self) -> list[Assets]:
        return [Assets.CLEAN_HTML]

    def list_outputs(self) -> list[Assets]:
        return [Assets.STRUCTURE_JSON]

    def run(self, inputs):
        clean_html = inputs[Assets.CLEAN_HTML]
        book_structure = create_book_structure(clean_html.read_text())
        book_structure_path = clean_html.parent / "book_structure.json"
        book_structure_path.write_text(book_structure.model_dump_json())
        return {Assets.STRUCTURE_JSON: book_structure_path}


class GenerateCardsStep(Step):
    name = "Generate cards"

    def list_inputs(self) -> list[Assets]:
        return [Assets.STRUCTURE_JSON]

    def list_outputs(self) -> list[Assets]:
        return [Assets.CARDS_JSONL]

    def run(self, inputs):
        book_structure = inputs[Assets.STRUCTURE_JSON]
        cards = generate_cards(book_structure)
        return {Assets.CARDS_JSONL: cards}


class Pipeline:
    def __init__(self, steps: list[Step]):
        self.steps = steps

    def main(self):
        # The steps are:
        # - Select which steps to run
        # - Configure the steps
        # - Ask the user to upload required input files
        # - Run the steps
        # - Allow the user to download the results

        with st.sidebar:

            st.header("Advanced configuration")

            st.subheader("Select which steps to run")
            steps_to_run = []
            for step in self.steps:
                if st.checkbox(step.name, True, key=f"run_{step.name}?"):
                    steps_to_run.append(step)

            st.subheader("Configure the steps")
            for step in steps_to_run:
                title = st.empty()
                if not step.configure():
                    title.write(f"##### {step.name}")

        st.subheader("Upload required input files")
        required_inputs = set()
        outputs = set()
        for step in steps_to_run:
            required_inputs.update(step.list_inputs())
            outputs.update(step.list_outputs())

        inputs = {}
        for i, asset in enumerate(required_inputs - outputs):
            inputs[asset] = asset.prompt(f"upload_{asset.name}_{i}")

        can_run = all(asset for asset in inputs.values())
        run = st.button("Run pipeline (requires all inputs)", type="primary", disabled=not can_run)

        if run:
            inputs = self.save_inputs(inputs)

            st.session_state["outputs"] = {}
            for step in steps_to_run:
                step_outputs = step.run(inputs)
                for asset, output in step_outputs.items():
                    inputs[asset] = output
                    st.session_state["outputs"][asset] = output

        # Allow the user to download the results
        outputs = st.session_state.get("outputs", {})
        if outputs:
            st.subheader("Download results")
            for asset, output in outputs.items():
                if isinstance(output, Path):
                    if output.is_file():
                        st.download_button(asset.name, output.open("rb"), file_name=output.name)
        if tmp_dir := st.session_state.get("tmp_dir", None):
            st.subheader("Download other outputs")
            self.download_directory(tmp_dir)

        with st.sidebar:
            # Enable to delete the temporary directory
            tmp_dir = st.session_state.get("tmp_dir", None)
            if tmp_dir is not None:
                st.divider()
                st.button(
                    "🗑️ Delete inputs and results from the server", on_click=self.delete_tmp_dir
                )

    def delete_tmp_dir(self):
        tmp_dir = st.session_state.get("tmp_dir", None)
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir)
            st.session_state["tmp_dir"] = None

    def save_inputs(self, inputs: dict[Assets, Any]):
        # We save the files in a temporary directory
        tmp_dir = st.session_state.get("tmp_dir", None)
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir)
        tmp_dir = Path(tempfile.mkdtemp(prefix="cards-pipeline-"))
        st.session_state["tmp_dir"] = tmp_dir

        all_file_names = []
        for file_or_files in inputs.values():
            if isinstance(file_or_files, list):
                for file in file_or_files:
                    all_file_names.append(file.name)
            else:
                all_file_names.append(file_or_files.name)

        if len(all_file_names) != len(set(all_file_names)):
            raise ValueError("All files must have unique names")

        processed_inputs = {}
        for asset, file_or_files in inputs.items():
            if isinstance(file_or_files, list):
                processed_inputs[asset] = []
                for file in file_or_files:
                    path = tmp_dir / file.name
                    path.write_bytes(file.read())
                    processed_inputs[asset].append(path)
            else:
                path = tmp_dir / file_or_files.name
                path.write_bytes(file_or_files.read())
                processed_inputs[asset] = path

        return processed_inputs

    def download_directory(self, directory: Path):
        # All files, subdirectories, etc.
        files = [f for f in directory.rglob("*") if f.is_file()]
        files.sort()
        selected_file = st.selectbox(
            "Select a file to download",
            files,
            format_func=lambda path: str(path.relative_to(directory)),
        )
        if selected_file is not None:
            st.download_button(
                selected_file.name, selected_file.open("rb"), file_name=selected_file.name
            )


if __name__ == "__main__":
    pipeline = Pipeline(
        [
            CleanEpubStep(),
            CreateBookStructureStep(),
            GenerateTocPdfStep(),
            GenerateSectionCardsPdfStep(),
            GenerateCardPdfsStep(),
            CombinePdfStep(),
        ]
    )
    pipeline.main()
