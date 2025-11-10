import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Literal

import streamlit as st
from dotenv import load_dotenv
from pydantic import BaseModel
from streamlit_pdf_viewer import pdf_viewer

from src.book_to_cards import (
    CardSet,
    analyze_book_structure,
    generate_cards_from_sections,
    generate_images_for_game,
    save_game_data,
)
from src.clean_epub import convert_epub_to_html, convert_html_to_clean_html
from src.pdf_combiner import combine_pdfs
from src.process_cards import generate_cards, generate_section_cards, generate_toc

load_dotenv()

st.set_page_config(
    page_title="📚 Book to Game Converter",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)


class State(BaseModel):
    work_dir: Path | None = None
    input_file: Path | None = None
    total_cards: int = 40
    generate_images: bool = True
    toc_only: bool = False
    output_file: Path | None = None
    card_format: Literal["A5", "A6"] = "A6"

    phase: str = "configure"


def configure_phase(state: State):
    """Phase 1: Upload file and configure all options"""
    st.header("Upload & Configure")

    uploaded_file = st.file_uploader(
        "Upload the EPUB or HTML of a book",
        type=["epub", "html"],
    )
    if uploaded_file:
        st.success(f"✅ Uploaded: {uploaded_file.name} ({uploaded_file.size:,} bytes)")

    output_type = st.radio(
        "What would you like to generate?",
        ["🎮 Complete Card Game", "📋 Table of Contents Only"],
        horizontal=True,
    )

    state.toc_only = output_type == "📋 Table of Contents Only"

    if not state.toc_only:
        state.total_cards = st.number_input(
            "Number of cards to generate",
            min_value=1,
            value=30,
            help="Total number of game cards to create",
        )
        formats = {
            "A6": "A6 (recommended, 4 per page)",
            "A5": "A5 (2 per page)",
        }
        state.card_format = st.radio(
            "How big should the cards be?",
            formats.keys(),
            format_func=lambda x: formats[x],
            horizontal=True,
        )

    state.generate_images = not st.checkbox(
        "Skip image generation",
        value=False,
    )

    # Start processing
    if st.button("🚀 Start Processing", type="primary", use_container_width=True):

        if not uploaded_file:
            st.error("Please upload a file first")
            return

        state.work_dir = Path(tempfile.mkdtemp(prefix="breaking_books_"))

        # Save uploaded file
        uploaded_file_path = state.work_dir / uploaded_file.name
        uploaded_file_path.write_bytes(uploaded_file.getvalue())
        state.input_file = uploaded_file_path

        state.phase = "processing"
        st.rerun()


class Stdout2Streamlit:
    """A context manager that redirects stdout to streamlit"""

    def __enter__(self):
        self.original_stdout = sys.stdout
        sys.stdout = self

    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout = self.original_stdout

    def write(self, *args, **kwargs):
        st.write(*args, **kwargs)

    def flush(self):
        pass


async def processing_phase(state: State):
    """Phase 2: Execute all processing steps"""
    st.header("⚡ Processing Your Book")

    # We do all the steps, simply by calling the imported function
    # BookGameProcessor is not to be used anymore
    input_path = state.input_file

    assert input_path is not None

    with st.status("Processing your book...", expanded=True) as status:
        with Stdout2Streamlit():

            print("Converting epub to html")
            if input_path.suffix == ".epub":
                cleaned_html_path = convert_epub_to_html(input_path)
                cleaned_html = cleaned_html_path.read_text(encoding="utf-8")
            elif input_path.suffix == ".html":
                cleaned_html = convert_html_to_clean_html(input_path.read_text(encoding="utf-8"))
            else:
                raise ValueError(f"Unsupported file type: {input_path.suffix}")

            print("Analyzing book structure")
            structure = analyze_book_structure(cleaned_html)

            if not state.toc_only:
                print("Generating cards")
                cards = await generate_cards_from_sections(
                    cleaned_html, structure, state.total_cards
                )
            else:
                cards = CardSet(card_definitions=[], language=structure.language)

            if state.generate_images:
                cards, structure = await generate_images_for_game(cards, structure)

            cards_file, structure_file = save_game_data(
                cards, structure, state.work_dir / f"{state.input_file.stem}_game"
            )

            pdf_paths = []
            pdf_paths += generate_cards(cards_file)
            pdf_paths += generate_section_cards(structure_file)
            pdf_paths += [generate_toc(structure_file)]

            state.output_file = state.input_file.with_name(
                f"{state.input_file.stem}_game_to_print.pdf"
            )
            combine_pdfs(
                pdf_paths, state.output_file, four_up=state.card_format == "A6", scale_a4=False
            )

        status.update(label="Book processed!", state="complete")

    state.phase = "results"
    st.rerun()


def results_phase(state: State):
    """Phase 3: Show results and downloads"""
    st.header("🎉 Your Game is Ready!")

    dl_col, pdf_col = st.columns([1, 4])

    with dl_col:
        st.download_button(
            label="Download PDF to print",
            data=state.output_file.read_bytes(),
            file_name=state.output_file.name,
            mime="application/pdf",
        )

    with pdf_col:
        pdf_viewer(state.output_file, annotations=[])


def main():
    st.title("📚 Breaking Books")
    st.markdown(
        "Welcome! This tool turns any non-fiction book into a collaborative, hands-on learning game."
    )

    # Sidebar
    with st.sidebar:
        st.header("About Breaking Books")
        st.markdown(
            "This tool transforms the solitary act of reading into an active, shared experience. "
            "The goal is to create a space for people to learn, build shared understanding, and connect."
        )

        st.header("🎲 How to Play")
        st.markdown(
            """
            **1. 👋 Welcome & Setup (10-15 mins)**
            - Gather your group (3-5 people is ideal).
            - Start with a welcome roundup: Why is everyone here? What's your interest in the book?
            - Designate a timekeeper.

            **2. 🗺️ The Landscape (5 mins)**
            - Each player chooses a book section they will "guide."
            - Everyone takes 5 minutes to read the enriched Table of Contents for *their chosen section*.

            **3. 🔄 Playing the Sections (The Core Loop)**
            - The section's guide reads its "Section Card" aloud.
            - Distribute all cards for that section.
            - Players discuss and place their cards on the table, drawing connections.
            - At the end of the section, the guide tells the story in **one minute sharp**.

            **4. 🏆 The Grand Finale**
            - After the final section, the most courageous person tells the story of the *entire book*.
            - Remember to take a picture of your beautiful creation! ✨
            """
        )

        st.header("⚙️ App Controls")

    # Route to current phase
    state = st.session_state.setdefault("state", State())
    if st.sidebar.button("🔄 Start again", use_container_width=True):
        state.phase = "configure"
        st.rerun()

    if state.phase == "configure":
        configure_phase(state)
    elif state.phase == "processing":
        asyncio.run(processing_phase(state))
    elif state.phase == "results":
        results_phase(state)


if __name__ == "__main__":
    main()
