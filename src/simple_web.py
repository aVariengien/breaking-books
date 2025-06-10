import asyncio
import atexit
import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from PIL import Image
from pydantic import BaseModel

from src.book_to_cards import (
    CardSet,
    analyze_book_structure,
    generate_cards_from_sections,
    generate_images_for_game,
    save_game_data,
)

# Import our pipeline functions
from src.clean_epub import add_unique_ids, convert_epub_to_html
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

    phase: str = "configure"

    # cleaned_html: str = ""
    # book_structure = None
    # cards = None
    # final_files: dict[str, bytes] = {}


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

    st.write(state)


# Cache expensive operations
@st.cache_data
def clean_epub_to_html_cached(epub_content_hash: str, epub_file_content: bytes) -> str:
    """Cached version of EPUB cleaning"""
    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp_epub:
        tmp_epub.write(epub_file_content)
        tmp_epub_path = Path(tmp_epub.name)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp_html:
        tmp_html_path = Path(tmp_html.name)

    script_dir = Path("src")
    lua_filter_path = script_dir / "remove_footnotes.lua"

    pandoc_command = [
        "pandoc",
        str(tmp_epub_path),
        "-o",
        str(tmp_html_path),
        "--standalone",
        f"--lua-filter={lua_filter_path}",
    ]

    subprocess.run(pandoc_command, check=True)
    html_content = tmp_html_path.read_text(encoding="utf-8")
    cleaned_html = add_unique_ids(html_content)

    tmp_epub_path.unlink()
    tmp_html_path.unlink()

    return cleaned_html


@st.cache_data
def analyze_book_structure_cached(html_hash: str, cleaned_html: str):
    """Cached version of book structure analysis"""
    return analyze_book_structure(cleaned_html)


class BookGameProcessor:
    """Handles the complete book-to-game conversion pipeline"""

    def __init__(self):
        self.work_dir: Path | None = None
        self.base_name: str = ""
        self.uploaded_file = None
        self.cleaned_html: str = ""
        self.book_structure = None
        self.cards = None
        self.total_cards = 40
        self.generate_images = True
        self.toc_only = False
        self.final_files: dict[str, bytes] = {}

    def setup_work_directory(self, filename: str) -> Path:
        """Create persistent working directory"""
        if self.work_dir is None:
            self.work_dir = Path(tempfile.mkdtemp(prefix="book_game_"))
            # Register cleanup
            atexit.register(self.cleanup)

        self.base_name = Path(filename).stem
        return self.work_dir

    def cleanup(self):
        """Clean up working directory"""
        if self.work_dir and self.work_dir.exists():
            shutil.rmtree(self.work_dir)
            self.work_dir = None

    def get_file_hash(self, file_content: bytes) -> str:
        """Get hash of file content for caching"""
        return hashlib.md5(file_content).hexdigest()

    def prepare_file(self, uploaded_file) -> str:
        """Step 1: Prepare and clean the uploaded file"""
        self.uploaded_file = uploaded_file
        self.setup_work_directory(uploaded_file.name)

        file_content = uploaded_file.getvalue()
        file_hash = self.get_file_hash(file_content)

        if uploaded_file.name.lower().endswith(".epub"):
            self.cleaned_html = clean_epub_to_html_cached(file_hash, file_content)
        else:
            self.cleaned_html = add_unique_ids(file_content.decode("utf-8"))

        return self.cleaned_html

    def analyze_structure(self) -> None:
        """Step 2: Analyze book structure"""
        html_hash = self.get_file_hash(self.cleaned_html.encode())
        self.book_structure = analyze_book_structure_cached(html_hash, self.cleaned_html)

    async def generate_cards(self) -> None:
        """Step 3: Generate game cards"""
        if not self.cards:  # Only generate if not already done
            self.cards = await generate_cards_from_sections(
                self.cleaned_html,
                self.book_structure,
                self.total_cards,
            )

    async def generate_images(self) -> None:
        """Step 4: Generate AI images"""
        if self.cards and self.generate_images:
            # Check if images already generated
            first_card = self.cards.card_definitions[0]
            if (
                not hasattr(first_card, "illustration")
                or first_card.illustration == "No image generated"
            ):
                self.cards, self.book_structure = await generate_images_for_game(
                    self.cards, self.book_structure
                )

    def generate_pdfs(self) -> dict[str, bytes]:
        """Step 5: Generate all PDFs and return as bytes"""
        final_files = {}

        if self.toc_only:
            # Generate TOC only
            structure_file = self.work_dir / "book_structure.json"
            with structure_file.open("w") as f:
                json.dump(self.book_structure.model_dump(), f, indent=2)

            toc_output_dir = generate_toc(structure_file)
            toc_pdf = list(toc_output_dir.glob("toc.pdf"))[0]
            final_files["toc_pdf"] = toc_pdf.read_bytes()

        else:
            # Generate complete game
            save_game_data(self.cards, self.book_structure, str(self.work_dir / self.base_name))

            cards_jsonl = self.work_dir / f"{self.base_name}.jsonl"
            structure_json = self.work_dir / f"book_structure_{self.base_name}.json"

            # Generate all PDF types
            cards_output_dir = generate_cards(cards_jsonl)
            sections_output_dir = generate_section_cards(structure_json)
            toc_output_dir = generate_toc(structure_json)

            # Combine all PDFs
            combined_pdf = self.work_dir / f"{self.base_name}_complete_game.pdf"
            all_pdfs_dir = self.work_dir / "all_pdfs"
            all_pdfs_dir.mkdir(exist_ok=True)

            for pdf_dir in [toc_output_dir, sections_output_dir, cards_output_dir]:
                for pdf_file in pdf_dir.glob("*.pdf"):
                    shutil.copy2(pdf_file, all_pdfs_dir)

            combine_pdfs(all_pdfs_dir, combined_pdf, four_up=False)

            # Store all files as bytes
            final_files["complete_pdf"] = combined_pdf.read_bytes()
            final_files["cards_jsonl"] = cards_jsonl.read_bytes()
            final_files["structure_json"] = structure_json.read_bytes()

            # Generate PNG export if images were created
            if self.generate_images:
                final_files["png_archive"] = self._create_png_archive()

        self.final_files = final_files
        return final_files

    def _create_png_archive(self) -> bytes:
        """Create ZIP archive of card PNGs"""
        png_dir = self.work_dir / "png_cards"
        png_dir.mkdir(exist_ok=True)

        for i, card in enumerate(self.cards.card_definitions):
            if hasattr(card, "illustration") and card.illustration != "No image generated":
                try:
                    image_data = base64.b64decode(card.illustration)
                    image = Image.open(BytesIO(image_data))
                    safe_title = "".join(
                        c for c in card.title if c.isalnum() or c in (" ", "-", "_")
                    ).strip()[:50]
                    png_file = png_dir / f"card_{i:03d}_{safe_title}.png"
                    image.save(png_file, "PNG")
                except Exception:
                    continue

        # Create ZIP
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            for png_file in png_dir.glob("*.png"):
                zip_file.write(png_file, png_file.name)

        return zip_buffer.getvalue()


class Stdout2Streamlit:
    """A context manager that redirects stdout to streamlit"""

    def __enter__(self):
        self.original_stdout = sys.stdout
        sys.stdout = self

    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout = self.original_stdout

    def write(self, *args, **kwargs):
        self.original_stdout.write(*args, **kwargs)
        st.write(*args, **kwargs)

    def flush(self):
        pass


def processing_phase(state: State):
    """Phase 2: Execute all processing steps"""
    st.header("⚡ Processing Your Book")
    st.write(state)
    st.write(st.session_state)

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

            output_file = state.input_file.with_name(f"{state.input_file.stem}_game_to_print.pdf")
            combine_pdfs(pdf_paths, output_file, four_up=False)

        status.update(label="Book processed!", state="complete")

    return

    processor = st.session_state.processor

    # Define steps based on configuration
    steps = [
        ("📤 Preparing file", "prepare"),
        ("🧹 Analyzing structure", "analyze"),
    ]

    if not processor.toc_only:
        steps.extend(
            [
                ("🎴 Generating cards", "cards"),
                ("🖼️ Creating images", "images") if processor.generate_images else None,
                ("📄 Building PDFs", "pdfs"),
            ]
        )
        steps = [s for s in steps if s is not None]
    else:
        steps.append(("📄 Building PDFs", "pdfs"))

    # Show progress
    current_step = st.session_state.current_step
    progress = min((current_step + 1) / len(steps), 1.0)
    st.progress(progress)

    # Show step status
    cols = st.columns(len(steps))
    for i, (step_name, step_id) in enumerate(steps):
        with cols[i]:
            if i < current_step:
                st.success(step_name)
            elif i == current_step:
                st.info(f"🔄 {step_name}")
            else:
                st.info(step_name)

    # Execute current step
    if current_step < len(steps):
        step_name, step_id = steps[current_step]

        try:
            if step_id == "prepare":
                with st.spinner("Preparing file..."):
                    processor.prepare_file(processor.uploaded_file)

            elif step_id == "analyze":
                with st.spinner("Analyzing book structure with AI..."):
                    processor.analyze_structure()
                    st.success(f"✅ Found {len(processor.book_structure.sections)} sections")

            elif step_id == "cards":
                with st.spinner(f"Generating {processor.total_cards} cards..."):
                    asyncio.run(processor.generate_cards())
                    st.success(f"✅ Generated {len(processor.cards.card_definitions)} cards!")

            elif step_id == "images":
                with st.spinner("Generating AI images (this takes a few minutes)..."):
                    asyncio.run(processor.generate_images())
                    st.success("✅ Generated all images!")

            elif step_id == "pdfs":
                with st.spinner("Creating printable PDFs..."):
                    processor.generate_pdfs()
                    st.success("✅ PDFs created!")

            # Move to next step
            st.session_state.current_step += 1
            if st.session_state.current_step >= len(steps):
                st.session_state.phase = "results"
                st.session_state.processing_complete = True

            # Auto-continue
            st.rerun()

        except Exception as e:
            st.error(f"❌ Error in {step_name}: {str(e)}")
            st.stop()


def results_phase():
    """Phase 3: Show results and downloads"""
    st.header("🎉 Your Game is Ready!")

    processor = st.session_state.processor

    if processor.toc_only:
        st.success("✅ Table of contents generated successfully!")

        st.download_button(
            label="📄 Download TOC PDF",
            data=processor.final_files["toc_pdf"],
            file_name=f"toc_{processor.base_name}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )

    else:
        st.success(
            f"✅ Complete game with {len(processor.cards.card_definitions)} cards generated!"
        )

        # Preview card
        if processor.cards.card_definitions:
            with st.expander("🎴 Preview First Card"):
                card = processor.cards.card_definitions[0]
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.write(f"**{card.title}**")
                    st.write(card.description)
                    if card.quotes:
                        st.quote(card.quotes[0])

                with col2:
                    if processor.generate_images and hasattr(card, "illustration"):
                        try:
                            image_data = base64.b64decode(card.illustration)
                            image = Image.open(BytesIO(image_data))
                            st.image(image, use_container_width=True)
                        except Exception:
                            st.info("Image preview not available")

        # Downloads
        st.subheader("📥 Download Your Game")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.download_button(
                label="📄 Complete Game PDF",
                data=processor.final_files["complete_pdf"],
                file_name=f"{processor.base_name}_complete_game.pdf",
                mime="application/pdf",
                type="primary",
            )

        with col2:
            st.download_button(
                label="🗃️ Cards Data (JSONL)",
                data=processor.final_files["cards_jsonl"],
                file_name=f"{processor.base_name}_cards.jsonl",
                mime="application/json",
            )

        with col3:
            st.download_button(
                label="📚 Book Structure (JSON)",
                data=processor.final_files["structure_json"],
                file_name=f"book_structure_{processor.base_name}.json",
                mime="application/json",
            )

        # PNG export
        if "png_archive" in processor.final_files:
            st.download_button(
                label="🖼️ Card Images (PNG Archive)",
                data=processor.final_files["png_archive"],
                file_name=f"{processor.base_name}_card_images.zip",
                mime="application/zip",
                use_container_width=True,
            )

    # Reset button
    if st.button("🔄 Process Another Book", use_container_width=True):
        # Cleanup current processor
        if st.session_state.processor:
            st.session_state.processor.cleanup()

        # Clear session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


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
    if state.phase == "configure":
        configure_phase(state)
    elif state.phase == "processing":
        processing_phase(state)
    elif state.phase == "results":
        results_phase(state)


if __name__ == "__main__":
    main()
