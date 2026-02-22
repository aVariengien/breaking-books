"""Card Generator — single-call Cerebras GLM-4.7 → BBGame JSON → Runware images.

Streamlit: run via `uv run streamlit run quality_tests/Home.py` and open this page.
"""

import asyncio
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st  # noqa: E402
from cerebras.cloud.sdk import Cerebras  # noqa: E402

from big_prompt import build_initial_query, build_system_prompt  # noqa: E402
from lib.models import BBGame, Config, WorkDir  # noqa: E402
from lib.streamlit_utils import in_streamlit  # noqa: E402
from tools.extract_book_content import extract_book_content  # noqa: E402
from tools.generate_images import DEFAULT_SIZE, _generate_image_async  # noqa: E402

DATA_DIR = ROOT / "data"
IMAGES_CACHE_DIR = ROOT / "quality_tests" / "output" / "images"

# ---------------------------------------------------------------------------
# Fast-mode prefix injected before the full agent system prompt.
# Tells the LLM to skip the agent loop and output JSON directly.
# ---------------------------------------------------------------------------
FAST_MODE_PREFIX = """\
⚠️  FAST DEBUG MODE — single call, no agent loop, no file I/O.

You are running inside a Streamlit debug tool. Ignore any instructions about
writing files to disk or calling quality_control(). Instead, follow these steps:

1. Execute Phase 1 (Map the book), Phase 2 (Visual Identity), and Phase 3
   (Write the cards) fully in your reasoning / thinking.
2. At the very end of your response, output the complete BBGame JSON object
   in a SINGLE ```json ... ``` code block — nothing after it.
3. Do NOT call quality_control(). Do NOT write any files. Skip Phase 4 entirely.

The BBGame JSON must be complete and valid. Start the code block with ```json
and close it with ```.

---

"""

CARD_TYPE_COLORS: dict[str, str] = {
    "default": "#4A90D9",
    "example": "#E8773D",
    "section": "#7B68EE",
    "question": "#D43F8D",
    "definition": "#20B2AA",
    "long_quote": "#B8860B",
    "diagram": "#3CB371",
    "enumeration": "#E05C30",
    "axis": "#8B6FBF",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_SUPPORTED_GLOBS = ("*.epub", "*.html", "*.htm", "*.md", "*.markdown")


def _book_files() -> list[Path]:
    files: list[Path] = []
    for pattern in _SUPPORTED_GLOBS:
        files.extend(DATA_DIR.glob(pattern))
    return sorted(files)


@st.cache_data(show_spinner="Loading book content…")
def _load_book(path_str: str) -> str:
    """Load book content: EPUB → pandoc extraction; HTML/MD → read directly."""
    path = Path(path_str)
    suffix = path.suffix.lower()
    if suffix == ".epub":
        return extract_book_content(path)
    # HTML and Markdown are used verbatim — no extraction needed.
    return path.read_text(encoding="utf-8")


def _build_image_prompt(card_dict: dict) -> str | None:
    """Return the Runware prompt for a card, or None if the card carries no image."""
    card_type = card_dict.get("type", "")
    if card_type in ("default", "example", "section"):
        illustration = card_dict.get("illustration", "")
        style = card_dict.get("illustration_style", "")
        if illustration:
            return f"{illustration}. Style: {style}" if style else illustration
    elif card_type in ("question", "definition", "long_quote"):
        return card_dict.get("texture") or None
    elif card_type == "diagram":
        return card_dict.get("diagram_prompt") or None
    return None


async def _generate_all_images_async(
    prompts: list[str | None],
    cache_dir: Path,
    progress_cb,
) -> list[Path | Exception | None]:
    """Generate all card images in parallel (max 4 concurrent) via Runware."""
    sem = asyncio.Semaphore(4)
    results: list[Path | Exception | None] = [None] * len(prompts)
    completed = 0
    total = sum(1 for p in prompts if p)

    async def _one(idx: int, prompt: str) -> None:
        nonlocal completed
        async with sem:
            try:
                path = await _generate_image_async(prompt, DEFAULT_SIZE, cache_dir)
                results[idx] = path
            except Exception as exc:  # noqa: BLE001
                results[idx] = exc
            finally:
                completed += 1
                if total > 0:
                    progress_cb(completed / total, completed, total)

    tasks = [_one(i, p) for i, p in enumerate(prompts) if p is not None]
    await asyncio.gather(*tasks)
    return results


def _extract_json_from_response(text: str) -> str | None:
    """Extract the last ```json ... ``` block, or fall back to the outermost {…}."""
    matches = re.findall(r"```json\s*([\s\S]*?)```", text)
    if matches:
        return matches[-1].strip()
    # Fallback: outermost { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return None


def _card_label(card_dict: dict) -> str:
    """Short display label for an expander header."""
    card_type = card_dict.get("type", "unknown").replace("_", " ").upper()
    title = (
        card_dict.get("title")
        or card_dict.get("word")
        or card_dict.get("question", "")[:70]
        or card_dict.get("quote", "")[:70]
        or ""
    )
    return f"[{card_type}] {title}" if title else f"[{card_type}]"


def _section_colors(game: BBGame, section_idx: int) -> tuple[str, str, str]:
    themes = game.visual_identity.section_themes
    if themes and section_idx < len(themes):
        t = themes[section_idx]
        return t.main_color, t.dark_color, t.accent_color
    return "#F5F5F5", "#222222", "#888888"


def _render_card(card_dict: dict, img: Path | Exception | None) -> None:
    """Render a single card's content inside an expander."""
    card_type = card_dict.get("type", "unknown")
    badge_color = CARD_TYPE_COLORS.get(card_type, "#888888")

    img_col, content_col = st.columns([2, 3], gap="medium")

    with img_col:
        if isinstance(img, Path) and img.exists():
            st.image(str(img), use_container_width=True)
        elif isinstance(img, Exception):
            st.warning(f"Image error: {img}")
        else:
            st.caption("_(no image for this card type)_")

    with content_col:
        st.markdown(
            f'<span style="background:{badge_color};color:#fff;padding:3px 10px;'
            f'border-radius:4px;font-size:0.78em;font-weight:700;letter-spacing:.04em;">'
            f"{card_type.replace('_', ' ').upper()}</span>",
            unsafe_allow_html=True,
        )
        st.markdown("")  # small gap

        if title := card_dict.get("title") or card_dict.get("word"):
            st.markdown(f"### {title}")

        # Ordered field display per card type
        fields_by_type: dict[str, list[tuple[str, str]]] = {
            "default": [("description", ""), ("quote", "Quote")],
            "example": [("description", ""), ("quote", "Quote")],
            "section": [("description", "")],
            "question": [("question", "")],
            "definition": [
                ("part_of_speech", "Part of speech"),
                ("etymology", "Etymology"),
                ("definition", ""),
                ("usage_example", "Usage"),
            ],
            "long_quote": [("quote", ""), ("context", "Context")],
            "diagram": [("caption", "Caption")],
            "axis": [
                ("description", ""),
                ("low_end", "Low end"),
                ("high_end", "High end"),
            ],
            "enumeration": [("description", "")],
        }

        for field, label in fields_by_type.get(card_type, []):
            val = card_dict.get(field, "")
            if not val:
                continue
            if label:
                st.markdown(f"**{label}:** {val}")
            else:
                st.markdown(val, unsafe_allow_html=True)

        # Enumeration items
        if card_type == "enumeration" and (items := card_dict.get("items")):
            for item in items:
                lbl = item.get("label", "")
                gloss = item.get("gloss", "")
                st.markdown(f"- **{lbl}**: {gloss}", unsafe_allow_html=True)

        if tag := card_dict.get("tag"):
            st.caption(f"Group tag: `{tag}`")


# ---------------------------------------------------------------------------
# Main Streamlit page
# ---------------------------------------------------------------------------


def run_streamlit() -> None:
    st.set_page_config(page_title="Card Generator", layout="wide")
    st.title("Card Generator")
    st.caption(
        "Build the full agent prompt → single Cerebras call (zai-glm-4.7) → "
        "parse BBGame JSON → generate images via Runware"
    )

    # ---- Sidebar: EPUB + Config ----
    with st.sidebar:
        st.header("Setup")

        book_files = _book_files()
        if not book_files:
            st.error(f"No supported book files found in `{DATA_DIR}` (epub, html, md)")
            st.stop()

        selected_file: Path = st.selectbox(  # type: ignore[assignment]
            "Book file", book_files, format_func=lambda p: p.name
        )

        st.divider()
        st.subheader("Card config")
        num_cards: int = st.slider("Target card count", 10, 80, 40, step=5)
        card_size: str = st.selectbox("Card size", ["A6", "A5"], index=0)  # type: ignore[assignment]
        language: str = st.text_input("Language", placeholder="Leave blank to match book")
        user_prefs: str = st.text_area(
            "User preferences", placeholder="e.g. Focus on practical examples, avoid jargon"
        )

        st.divider()
        st.subheader("Images")
        generate_images_flag: bool = st.checkbox("Generate images (Runware)", value=True)
        if generate_images_flag and not os.environ.get("RUNWARE_API_KEY"):
            st.warning("RUNWARE_API_KEY not set — images will be skipped.")
            generate_images_flag = False

    config = Config(
        num_cards=num_cards,
        card_size=card_size,  # type: ignore[arg-type]
        language=language.strip() or None,
        max_qc_calls=3,
        user_preferences=user_prefs,
    )

    # Detect file change to reset session state
    file_key = str(selected_file)
    if st.session_state.get("_file_key") != file_key:
        for k in ("llm_response", "game", "image_paths"):
            st.session_state.pop(k, None)
        st.session_state["_file_key"] = file_key

    # ---- Step 1: Load book ----
    suffix = selected_file.suffix.lower()
    step1_label = (
        "Step 1 — Extract book (EPUB → HTML)" if suffix == ".epub" else "Step 1 — Load book"
    )
    st.subheader(step1_label)

    book_html = _load_book(str(selected_file))
    action = "Extracted" if suffix == ".epub" else "Loaded"
    preview_lang = "html" if suffix in (".html", ".htm", ".epub") else "markdown"
    st.success(f"{action} **{len(book_html):,}** characters from `{selected_file.name}`")

    with st.expander("Preview (first 3 000 chars)"):
        st.code(book_html[:3000], language=preview_lang)

    # ---- Step 2: Build prompt ----
    st.subheader("Step 2 — Build prompt")

    with tempfile.TemporaryDirectory() as _tmp:
        work_dir = WorkDir.create(Path(_tmp))
        system_prompt = build_system_prompt(config, work_dir)
        initial_query = build_initial_query(book_html)
        base_prompt = system_prompt + "\n\n" + initial_query

    full_prompt = FAST_MODE_PREFIX + base_prompt

    c1, c2 = st.columns(2)
    c1.metric("Total prompt length", f"{len(full_prompt):,} chars")
    c2.metric("Estimated tokens (~4 chars/tok)", f"{len(full_prompt) // 4:,}")

    with st.expander("Show full system prompt"):
        st.text_area("Prompt", full_prompt, height=400, disabled=True, label_visibility="collapsed")

    # ---- Step 3: Cerebras call ----
    st.subheader("Step 3 — Generate with Cerebras `zai-glm-4.7`")

    api_key = os.environ.get("CEREBRAS_API_KEY", "")
    if not api_key:
        st.error("CEREBRAS_API_KEY not found in environment. Add it to your `.env` file.")
        st.stop()

    if st.button("Generate card deck", type="primary", use_container_width=True):
        for k in ("llm_response", "game", "image_paths"):
            st.session_state.pop(k, None)

        client = Cerebras(api_key=api_key)
        stream_box = st.empty()
        full_text = ""

        with st.spinner("Calling Cerebras — this may take a few minutes for long books…"):
            try:
                stream = client.chat.completions.create(
                    model="zai-glm-4.7",
                    messages=[
                        {"role": "system", "content": full_prompt},
                        {"role": "user", "content": "Generate the card deck now."},
                    ],
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        full_text += delta.content
                        # Show trailing window so the UI stays responsive
                        stream_box.text_area(
                            "Response (streaming…)",
                            value=full_text[-4000:],
                            height=260,
                            disabled=True,
                            label_visibility="collapsed",
                        )
            except Exception as exc:  # noqa: BLE001
                st.error(f"Cerebras API error: {exc}")
                st.stop()

        stream_box.empty()
        st.session_state["llm_response"] = full_text
        st.success(f"Received **{len(full_text):,}** characters from Cerebras.")

    # Show stored response
    if response := st.session_state.get("llm_response"):
        with st.expander(f"Full LLM response ({len(response):,} chars)"):
            st.text_area(
                "Response",
                response,
                height=500,
                disabled=True,
                label_visibility="collapsed",
            )

        # ---- Step 4: Parse JSON ----
        st.subheader("Step 4 — Parse BBGame JSON")

        if "game" not in st.session_state:
            raw_json = _extract_json_from_response(response)
            if raw_json is None:
                st.error(
                    "No JSON block found in the response. "
                    "The model may not have followed the output instructions. "
                    "Check the full response above."
                )
                st.stop()

            try:
                data = json.loads(raw_json)
                game = BBGame.model_validate(data)
                st.session_state["game"] = game
            except json.JSONDecodeError as exc:
                st.error(f"JSON parse error: {exc}")
                with st.expander("Raw JSON (first 4 000 chars)"):
                    st.code(raw_json[:4000], language="json")
                st.stop()
            except Exception as exc:  # noqa: BLE001
                st.error(f"BBGame validation error: {exc}")
                with st.expander("Raw JSON (first 4 000 chars)"):
                    st.code(raw_json[:4000], language="json")
                st.stop()

        game: BBGame = st.session_state["game"]
        n_sections = len(game.visual_identity.section_themes)
        st.success(
            f"Parsed **{len(game.cards)}** cards across **{n_sections}** sections. "
            f"Fonts: `{game.visual_identity.title_font}` / `{game.visual_identity.body_font}`"
        )

        with st.expander("Full BBGame JSON"):
            st.json(game.model_dump())

        # ---- Step 5: Generate images ----
        if generate_images_flag and "image_paths" not in st.session_state:
            st.subheader("Step 5 — Generate images (Runware)")
            IMAGES_CACHE_DIR.mkdir(parents=True, exist_ok=True)

            card_dicts = [c.model_dump() for c in game.cards]
            prompts = [_build_image_prompt(c) for c in card_dicts]
            n_images = sum(1 for p in prompts if p)

            if n_images == 0:
                st.info("No image prompts found in this deck.")
                st.session_state["image_paths"] = [None] * len(prompts)
            else:
                st.info(f"Generating **{n_images}** images…")
                progress_bar = st.progress(0.0)
                status_text = st.empty()

                def _on_progress(frac: float, done: int, total: int) -> None:
                    progress_bar.progress(frac)
                    status_text.caption(f"Generated {done} / {total} images")

                try:
                    paths = asyncio.run(
                        _generate_all_images_async(prompts, IMAGES_CACHE_DIR, _on_progress)
                    )
                    st.session_state["image_paths"] = paths
                    errors = [p for p in paths if isinstance(p, Exception)]
                    if errors:
                        st.warning(f"{len(errors)} image(s) failed to generate.")
                    else:
                        st.success("All images generated.")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Image generation failed: {exc}")
                    st.session_state["image_paths"] = [None] * len(prompts)

        # ---- Step 6: Display cards ----
        st.subheader("Step 6 — Card deck")

        image_paths: list = st.session_state.get("image_paths") or [None] * len(game.cards)
        card_dicts = [c.model_dump() for c in game.cards]

        # Group cards by section index (preserving order)
        seen_sections: list[int] = []
        sections: dict[int, list[tuple[int, dict]]] = {}
        for i, card in enumerate(card_dicts):
            s = card.get("section", 0)
            if s not in sections:
                seen_sections.append(s)
                sections[s] = []
            sections[s].append((i, card))

        for section_idx in seen_sections:
            cards_in_section = sections[section_idx]
            main_color, dark_color, _accent = _section_colors(game, section_idx)

            # Find the SectionCard title if present
            section_title = f"Section {section_idx}"
            for _, c in cards_in_section:
                if c.get("type") == "section" and c.get("title"):
                    section_title = c["title"]
                    break

            st.markdown(
                f'<div style="background:{main_color};color:{dark_color};'
                f"padding:10px 16px;border-radius:8px;margin:20px 0 8px 0;"
                f'font-weight:700;font-size:1.05em;">{section_title}</div>',
                unsafe_allow_html=True,
            )

            for card_global_idx, card_dict in cards_in_section:
                img = image_paths[card_global_idx] if card_global_idx < len(image_paths) else None
                label = _card_label(card_dict)

                with st.expander(label, expanded=False):
                    _render_card(card_dict, img)


if in_streamlit():
    run_streamlit()
else:
    print("Run with: uv run streamlit run quality_tests/Home.py")
