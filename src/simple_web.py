import sys
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from pydantic import BaseModel

from src.book_to_cards import (
    CardSet,
    analyze_book_structure,
    generate_cards_from_sections,
    generate_images_for_game,
    save_game_data,
)

# Import our pipeline functions
from src.clean_epub import convert_epub_to_html
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

    phase: str = "configure"


def configure_phase(state: State):
    """Phase 1: Upload file and configure all options"""
    st.header("📚 Configure Your Book Game")

    uploaded_file = st.file_uploader(
        "Upload the EPUB of a book",
        type=["epub"],
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
            value=40,
            help="Total number of game cards to create",
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


def processing_phase(state: State):
    """Phase 2: Execute all processing steps"""
    st.header("⚡ Processing Your Book")

    # We do all the steps, simply by calling the imported function
    # BookGameProcessor is not to be used anymore
    input_path = state.input_file

    assert input_path is not None

    with st.status("Processing your book...", expanded=True) as status:
        with Stdout2Streamlit():

            print("Converting epub to html")
            cleaned_html = convert_epub_to_html(input_path)
            print("Analyzing book structure")
            structure = analyze_book_structure(cleaned_html.read_text())

            if not state.toc_only:
                print("Generating cards")
                cards = generate_cards_from_sections(cleaned_html, structure, state.total_cards)
            else:
                cards = CardSet(card_definitions=[])

            if state.generate_images:
                cards, structure = generate_images_for_game(cards, structure)

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
            combine_pdfs(pdf_paths, state.output_file, four_up=False, scale_a4=False)

        status.update(label="Book processed!", state="complete")

    state.phase = "results"
    st.rerun()


def results_phase(state: State):
    """Phase 3: Show results and downloads"""
    st.header("🎉 Your Game is Ready!")

    st.download_button(
        label="Download cards to print",
        data=state.output_file.read_bytes(),
        file_name=state.output_file.name,
        mime="application/pdf",
    )


def main():
    st.title("📚 Book to Game Converter")
    st.markdown("Transform your favorite books into physical card games! 🎮")

    # Sidebar
    with st.sidebar:
        st.header("ℹ️ How it Works")
        st.markdown(
            """
        1. **Upload** an EPUB or HTML book
        2. **Configure** your game options
        3. **Watch** the AI process your book
        4. **Download** your complete game!
        """
        )

    # Route to current phase
    state = st.session_state.setdefault("state", State())
    st.sidebar.write(state)

    if state.phase == "configure":
        configure_phase(state)
    elif state.phase == "processing":
        processing_phase(state)
    elif state.phase == "results":
        results_phase(state)


if __name__ == "__main__":
    main()
