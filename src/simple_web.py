import asyncio
import base64
import json
import shutil
import subprocess
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from PIL import Image

from src.book_to_cards import (
    analyze_book_structure,
    generate_cards_from_sections,
    generate_images_for_game,
    save_game_data,
)

# Import our pipeline functions
from src.clean_epub import add_unique_ids
from src.pdf_combiner import combine
from src.process_cards import generate_cards, generate_section_cards, generate_toc

load_dotenv()

st.set_page_config(
    page_title="📚 Book to Game Converter",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state():
    """Initialize session state variables"""
    defaults = {
        "current_step": "upload",
        "uploaded_file": None,
        "cleaned_html": None,
        "book_structure": None,
        "cards": None,
        "total_cards": 40,
        "generate_images": True,
        "toc_only": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def show_progress_bar():
    """Show progress through the pipeline"""
    steps = [
        ("upload", "📤 Upload Book"),
        ("clean", "🧹 Clean & Analyze"),
        ("generate", "🎴 Generate Content"),
        ("pdf", "📄 Create PDFs"),
        ("download", "⬇️ Download"),
    ]

    current_idx = next(
        (i for i, (step, _) in enumerate(steps) if step == st.session_state.current_step), 0
    )

    progress = (current_idx + 1) / len(steps)
    st.progress(progress)

    # Show current step
    cols = st.columns(len(steps))
    for i, (step, label) in enumerate(steps):
        with cols[i]:
            if i <= current_idx:
                st.success(label)
            else:
                st.info(label)


def clean_epub_to_html(epub_file_content: bytes) -> str:
    """Clean EPUB file and return HTML content"""
    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp_epub:
        tmp_epub.write(epub_file_content)
        tmp_epub_path = Path(tmp_epub.name)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp_html:
        tmp_html_path = Path(tmp_html.name)

    # Use pandoc to convert
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

    # Read and add unique IDs
    html_content = tmp_html_path.read_text(encoding="utf-8")
    cleaned_html = add_unique_ids(html_content)

    # Cleanup
    tmp_epub_path.unlink()
    tmp_html_path.unlink()

    return cleaned_html


def upload_step():
    """Step 1: Upload book file"""
    st.header("📤 Upload Your Book")

    uploaded_file = st.file_uploader(
        "Choose an EPUB or HTML file",
        type=["epub", "html", "htm"],
        help="Upload either an EPUB file (will be cleaned) or a pre-cleaned HTML file",
    )

    if uploaded_file:
        st.session_state.uploaded_file = uploaded_file

        # Show file info
        st.success(f"✅ Uploaded: {uploaded_file.name} ({uploaded_file.size:,} bytes)")

        if st.button("Continue to Book Analysis", type="primary"):
            st.session_state.current_step = "clean"
            st.rerun()


def clean_and_analyze_step():
    """Step 2: Clean EPUB and analyze book structure"""
    st.header("🧹 Clean & Analyze Book")

    if not st.session_state.uploaded_file:
        st.error("Please upload a file first")
        if st.button("← Back to Upload"):
            st.session_state.current_step = "upload"
            st.rerun()
        return

    with st.spinner("Processing book..."):
        # Handle EPUB vs HTML
        if st.session_state.uploaded_file.name.lower().endswith(".epub"):
            st.session_state.cleaned_html = clean_epub_to_html(
                st.session_state.uploaded_file.getvalue()
            )
        else:
            # HTML file - add IDs if needed
            html_content = st.session_state.uploaded_file.getvalue().decode("utf-8")
            st.session_state.cleaned_html = add_unique_ids(html_content)

    # Analyze book structure
    with st.spinner("Analyzing book structure with AI..."):
        st.session_state.book_structure = analyze_book_structure(st.session_state.cleaned_html)

    # Show analysis results
    st.success("✅ Book analyzed successfully!")

    structure = st.session_state.book_structure
    st.info(
        f"Found **{len(structure.sections)}** sections with **{sum(len(s.chapters) for s in structure.sections)}** chapters"
    )

    # Show sections
    with st.expander("📖 Book Structure Preview"):
        for i, section in enumerate(structure.sections):
            st.subheader(f"Section {i+1}: {section.section_name}")
            st.write(
                section.section_introduction[:200] + "..."
                if len(section.section_introduction) > 200
                else section.section_introduction
            )
            st.write(f"**Chapters:** {', '.join([c.chapter_name for c in section.chapters])}")

    # Options for next step
    st.subheader("Choose Your Output")

    col1, col2 = st.columns(2)

    with col1:
        st.info(
            "**📋 TOC Only**\nGenerate just the table of contents and section summaries as a PDF"
        )
        if st.button("Generate TOC Only", type="secondary"):
            st.session_state.toc_only = True
            st.session_state.current_step = "pdf"
            st.rerun()

    with col2:
        st.info("**🎮 Full Game**\nGenerate cards, images, and complete game materials")
        if st.button("Generate Full Game", type="primary"):
            st.session_state.toc_only = False
            st.session_state.current_step = "generate"
            st.rerun()


def generate_content_step():
    """Step 3: Generate cards and images"""
    if st.session_state.toc_only:
        st.session_state.current_step = "pdf"
        st.rerun()
        return

    st.header("🎴 Generate Game Content")

    # Configuration options
    col1, col2 = st.columns(2)

    with col1:
        st.session_state.total_cards = st.number_input(
            "Number of cards to generate",
            min_value=10,
            max_value=100,
            value=40,
            help="Total number of game cards to create",
        )

    with col2:
        st.session_state.generate_images = st.checkbox(
            "Generate AI images",
            value=True,
            help="Generate AI images for cards and sections (slower but prettier)",
        )

    if st.button("Start Generation", type="primary"):
        with st.spinner("Generating cards from book sections..."):
            # Generate cards
            st.session_state.cards = asyncio.run(
                generate_cards_from_sections(
                    st.session_state.cleaned_html,
                    st.session_state.book_structure,
                    st.session_state.total_cards,
                )
            )

            st.success(f"✅ Generated {len(st.session_state.cards.card_definitions)} cards!")

        if st.session_state.generate_images:
            with st.spinner("Generating AI images (this may take a few minutes)..."):
                st.session_state.cards, st.session_state.book_structure = asyncio.run(
                    generate_images_for_game(
                        st.session_state.cards, st.session_state.book_structure
                    )
                )
                st.success("✅ Generated all images!")

        # Show preview
        st.subheader("🎴 Card Preview")
        if st.session_state.cards.card_definitions:
            preview_card = st.session_state.cards.card_definitions[0]

            col1, col2 = st.columns([2, 1])
            with col1:
                st.write(f"**{preview_card.title}**")
                st.write(preview_card.description)
                if preview_card.quotes:
                    st.write("*Sample quote:*")
                    st.quote(preview_card.quotes[0])

            with col2:
                if (
                    st.session_state.generate_images
                    and hasattr(preview_card, "illustration")
                    and preview_card.illustration != "No image generated"
                ):
                    try:
                        image_data = base64.b64decode(preview_card.illustration)
                        image = Image.open(BytesIO(image_data))
                        st.image(image, caption="Generated card image", use_container_width=True)
                    except Exception:
                        st.info("Image preview not available")

        st.session_state.current_step = "pdf"
        st.rerun()


def pdf_generation_step():
    """Step 4: Generate PDFs"""
    st.header("📄 Generate PDFs")

    # Create temporary files for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        base_name = st.session_state.uploaded_file.name.split(".")[0]

        if st.session_state.toc_only:
            # Generate TOC only
            with st.spinner("Generating table of contents PDF..."):
                # Save book structure
                structure_file = temp_path / "book_structure.json"
                with structure_file.open("w") as f:
                    json.dump(st.session_state.book_structure.model_dump(), f, indent=2)

                # Generate TOC PDF
                toc_output_dir = generate_toc(structure_file)

                st.success("✅ TOC PDF generated!")

                # Find and offer download
                toc_pdf = list(toc_output_dir.glob("toc.pdf"))[0]

                with toc_pdf.open("rb") as f:
                    st.download_button(
                        label="📄 Download TOC PDF",
                        data=f.read(),
                        file_name=f"toc_{base_name}.pdf",
                        mime="application/pdf",
                        type="primary",
                    )

        else:
            # Generate full game
            with st.spinner("Generating complete game files..."):
                # Save cards and structure
                save_game_data(
                    st.session_state.cards,
                    st.session_state.book_structure,
                    str(temp_path / base_name),
                )

                # Generate all PDFs
                cards_jsonl = temp_path / f"{base_name}.jsonl"
                structure_json = temp_path / f"book_structure_{base_name}.json"

                cards_output_dir = generate_cards(cards_jsonl)
                sections_output_dir = generate_section_cards(structure_json)
                toc_output_dir = generate_toc(structure_json)

                # Combine all PDFs
                combined_pdf = temp_path / f"{base_name}_complete_game.pdf"

                # Collect all PDFs
                all_pdfs_dir = temp_path / "all_pdfs"
                all_pdfs_dir.mkdir()

                for pdf_dir in [toc_output_dir, sections_output_dir, cards_output_dir]:
                    for pdf_file in pdf_dir.glob("*.pdf"):
                        shutil.copy2(pdf_file, all_pdfs_dir)

                combine(all_pdfs_dir, combined_pdf, four_up=False)

                st.success("✅ Complete game generated!")

            # Download section
            st.subheader("📥 Download Your Game")

            col1, col2, col3 = st.columns(3)

            with col1:
                # Combined PDF
                with combined_pdf.open("rb") as f:
                    st.download_button(
                        label="📄 Complete Game PDF",
                        data=f.read(),
                        file_name=f"{base_name}_complete_game.pdf",
                        mime="application/pdf",
                        type="primary",
                    )

            with col2:
                # Cards JSONL
                with cards_jsonl.open("rb") as f:
                    st.download_button(
                        label="🗃️ Cards Data (JSONL)",
                        data=f.read(),
                        file_name=f"{base_name}_cards.jsonl",
                        mime="application/json",
                    )

            with col3:
                # Book structure JSON
                with structure_json.open("rb") as f:
                    st.download_button(
                        label="📚 Book Structure (JSON)",
                        data=f.read(),
                        file_name=f"book_structure_{base_name}.json",
                        mime="application/json",
                    )

            # PNG Export option
            if st.session_state.generate_images:
                st.subheader("🖼️ Export Card Images as PNG")

                if st.button("Generate PNG Archive"):
                    with st.spinner("Creating PNG files..."):
                        png_dir = temp_path / "png_cards"
                        png_dir.mkdir()

                        for i, card in enumerate(st.session_state.cards.card_definitions):
                            if (
                                hasattr(card, "illustration")
                                and card.illustration != "No image generated"
                            ):
                                try:
                                    image_data = base64.b64decode(card.illustration)
                                    image = Image.open(BytesIO(image_data))

                                    # Save as PNG with safe filename
                                    safe_title = "".join(
                                        c for c in card.title if c.isalnum() or c in (" ", "-", "_")
                                    ).strip()[:50]
                                    png_file = png_dir / f"card_{i:03d}_{safe_title}.png"
                                    image.save(png_file, "PNG")

                                except Exception as e:
                                    st.warning(f"Could not export card {i}: {e}")

                        # Create ZIP archive
                        zip_buffer = BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                            for png_file in png_dir.glob("*.png"):
                                zip_file.write(png_file, png_file.name)

                        st.download_button(
                            label="🗂️ Download PNG Archive",
                            data=zip_buffer.getvalue(),
                            file_name=f"{base_name}_card_images.zip",
                            mime="application/zip",
                        )

    # Option to start over
    if st.button("🔄 Process Another Book"):
        # Clear session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


def main():
    init_session_state()

    # Title and description
    st.title("📚 Book to Game Converter")
    st.markdown("Transform your favorite books into physical card games! 🎮")

    # Sidebar with info
    with st.sidebar:
        st.header("ℹ️ How it Works")
        st.markdown(
            """
        1. **Upload** an EPUB or HTML book
        2. **Analyze** structure and extract key concepts
        3. **Generate** game cards with AI
        4. **Create** printable PDFs
        5. **Download** your complete game!

        **Features:**
        - 🎴 AI-generated concept cards
        - 🖼️ Custom illustrations
        - 📄 Print-ready PDFs
        - 📋 Table of contents option
        - 🖼️ PNG export for cards
        """
        )

        st.header("🎯 Tips")
        st.markdown(
            """
        - **EPUB files** work best (auto-cleaned)
        - **40 cards** is usually perfect for most books
        - **Images** make it prettier but take longer
        - **TOC-only** is great for study guides
        """
        )

    # Progress indicator
    show_progress_bar()
    st.divider()

    # Main content based on current step
    if st.session_state.current_step == "upload":
        upload_step()
    elif st.session_state.current_step == "clean":
        clean_and_analyze_step()
    elif st.session_state.current_step == "generate":
        generate_content_step()
    elif st.session_state.current_step == "pdf":
        pdf_generation_step()


if __name__ == "__main__":
    main()
