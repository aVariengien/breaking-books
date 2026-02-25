"""Streamlit UI for Breaking Books v2."""

import asyncio
import dataclasses
import json
import random
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from slugify import slugify

from agent import run_agent
from lib import log
from lib.models import BBGame, Config, OutDir, WorkDir
from tools.extract_book_content import load_book
from tools.merge_pdfs import merge_pdfs_to_print
from tools.render_template import cards_json_to_pdfs
from web.utils import deck_viewer, render_agent_log, render_message, update_status_for_message

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

_HOW_TO_PLAY = """
**1. 👋 Welcome & Setup** *(10–15 min)*
- Gather your group (3–5 people is ideal).
- Start with a welcome roundup: Why is everyone here? What's your interest in the book?
- Designate a timekeeper.

**2. 🔄 Playing the Sections** *(the core loop)*
- Each player chooses a book section they will "guide."
- The section's guide reads the Section Card aloud.
- Distribute all cards for that section.
- Players discuss and place their cards on the table, drawing connections.
- At the end, the guide tells the section story in **one minute sharp**.

**3. 🏆 The Grand Finale**
- After all sections, the most courageous person tells the story of the *entire book*.
- Remember to take a picture of your beautiful creation! ✨
"""

# ------------------------------------------------------------------
# Session state defaults
# ------------------------------------------------------------------

_DEFAULTS: dict[str, Any] = {
    "uploaded_path": None,
    "book_html": None,
    "config": None,
    "work_dir": None,
    "out_dir": None,
    "messages": [],
    "agent_done": False,
    "pending_instructions": None,
    # Set to True as soon as Generate is clicked, to hide config on next rerun
    "generation_started": False,
    "_pending_file_path": None,
    "_pending_config": None,
}


def _init_state() -> None:
    for key, default in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


# ------------------------------------------------------------------
# Message serialization
# ------------------------------------------------------------------


def _serialize_message(message: Any) -> dict:
    """Convert an SDK dataclass message to a JSON-serializable dict.

    Preserves the original field names by using dataclasses.asdict(), and tags
    each message and its content blocks with ``__type__`` (the class name) so
    the renderer can dispatch without a separate schema.
    """
    d = dataclasses.asdict(message)
    d["__type__"] = type(message).__name__
    # Tag nested content blocks (AssistantMessage / UserMessage)
    if hasattr(message, "content") and isinstance(message.content, list):
        for block, block_d in zip(message.content, d.get("content", [])):
            if dataclasses.is_dataclass(block) and isinstance(block_d, dict):
                block_d["__type__"] = type(block).__name__
    return d


# ------------------------------------------------------------------
# Agent log download
# ------------------------------------------------------------------


def _maybe_log_download(messages: list[dict], *, key: str) -> None:
    """Show a download button for the agent log JSON."""
    data = json.dumps(messages, indent=2, ensure_ascii=False).encode()
    st.download_button(
        "⬇ Agent log (JSON)",
        data=data,
        file_name="agent_log.json",
        mime="application/json",
        key=f"dl_agent_log_{key}",
    )


# ------------------------------------------------------------------
# Agent streaming
# ------------------------------------------------------------------


def _result_summary(messages: list[dict]) -> str:
    """Extract the cost/turn/duration summary from a result message."""
    result = next((m for m in reversed(messages) if m.get("__type__") == "ResultMessage"), None)
    if not result:
        return ""
    cost = f"${result['total_cost_usd']:.4f}" if result.get("total_cost_usd") else "N/A"
    dur = result.get("duration_ms", 0) / 1000
    return f"{result['num_turns']} turns · {cost} · {dur:.0f}s"


def _stream_agent(
    book_html: str,
    config: Config,
    work_dir: WorkDir,
    out_dir: OutDir,
    *,
    resume: bool = False,
    instructions: str = "",
) -> list[dict]:
    """Run the agent, streaming all messages inside a single st.status() container."""
    new_messages: list[dict] = []
    last_action_t: list[float] = [time.monotonic()]

    with st.status(
        "Resuming…" if resume else "Generating your deck…",
        expanded=True,
    ) as status:

        async def _run() -> None:
            async for message in run_agent(
                book_html, config, work_dir, out_dir, resume=resume, instructions=instructions
            ):
                log.log_message(message)
                serialized = _serialize_message(message)
                new_messages.append(serialized)

                elapsed = time.monotonic() - last_action_t[0]
                update_status_for_message(status, serialized, elapsed=elapsed)
                last_action_t[0] = time.monotonic()

                render_message(serialized)

        asyncio.run(_run())

        is_error = any(m.get("is_error") for m in new_messages if m.get("kind") == "result")
        summary = _result_summary(new_messages)
        status.update(
            label=f"Generation failed — {summary}" if is_error else f"Agent log — {summary}",
            state="error" if is_error else "complete",
            expanded=False,
        )

    return new_messages


# ------------------------------------------------------------------
# Versioned deck helpers
# ------------------------------------------------------------------


def _deck_versions(out_dir: OutDir) -> list[Path]:
    """Return all deck-vNNN.pdf files in out_dir, sorted by version number."""
    return sorted(
        out_dir.root.glob("deck-v*.pdf"),
        key=lambda p: int(p.stem.split("-v")[1]),
    )


def _next_deck_path(out_dir: OutDir) -> Path:
    """Return the path for the next (not-yet-created) deck version."""
    existing = _deck_versions(out_dir)
    next_v = int(existing[-1].stem.split("-v")[1]) + 1 if existing else 0
    return out_dir.root / f"deck-v{next_v:03d}.pdf"


# ------------------------------------------------------------------
# Results display
# ------------------------------------------------------------------


def _show_results(
    work_dir: WorkDir,
    out_dir: OutDir,
    config: Config,
    *,
    new_version: bool = False,
) -> None:
    """Load BBGame from cards.json and display metrics + deck viewer."""
    cards_path = work_dir.cards_json
    if not cards_path.exists():
        st.warning("No cards.json found yet.")
        return

    try:
        game = BBGame.model_validate_json(cards_path.read_text(encoding="utf-8"))
    except Exception as e:
        st.error(f"Failed to parse cards.json: {e}")
        return

    st.divider()

    # Summary metrics
    card_types: dict[str, int] = {}
    for card in game.cards:
        label = str(card.model_dump().get("type", "unknown"))
        card_types[label] = card_types.get(label, 0) + 1

    col1, col2, col3 = st.columns(3)
    col1.metric("Cards", len(game.cards))
    col2.metric("Sections", len(game.visual_identity.section_themes))
    col3.metric("Types", len(card_types))

    # Render card PDFs when needed
    renders_dir = work_dir.renders_dir
    existing_card_pdfs = sorted(renders_dir.glob("card-*.pdf"))
    if (len(existing_card_pdfs) != len(game.cards) or new_version) and game.cards:
        with st.spinner("Rendering cards to PDF…"):
            existing_card_pdfs = cards_json_to_pdfs(cards_path, renders_dir, out_dir.images_dir)

    # Build a new versioned deck if needed
    versions = _deck_versions(out_dir)
    if existing_card_pdfs and (not versions or new_version):
        deck_path = _next_deck_path(out_dir)
        with st.spinner(f"Building {deck_path.name}…"):
            merge_pdfs_to_print(existing_card_pdfs, deck_path, card_size=config.card_size)
        versions = _deck_versions(out_dir)

    # Deck viewer: version selector + PDF download + JSON download + PDF preview
    # Card images ZIP is offered via deck_viewer when card PDFs are available
    deck_viewer(
        versions,
        cards_json_path=cards_path,
        card_pdfs=existing_card_pdfs if existing_card_pdfs else None,
        key_prefix="gen",
    )


# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------


def _sidebar() -> None:
    """Render the sidebar: about, how to play, and new-book reset at the bottom."""
    with st.sidebar:
        st.title("Breaking Books")
        st.markdown(
            "Turn any non-fiction book into a printable flashcard deck. "
            "An AI agent reads the book, designs the cards, and iterates until they're good."
        )

        st.header("How to Play")
        st.markdown(_HOW_TO_PLAY)

        # New book button pinned to the bottom of the sidebar (after all other content)
        if st.session_state.get("generation_started"):
            st.divider()
            if st.button("New book", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()


# ------------------------------------------------------------------
# Config section (main area)
# ------------------------------------------------------------------


def _config_section() -> tuple[Any, int, str, str, str | None, int, str]:
    """Render config widgets. Returns (uploaded_file, num_cards, card_size, model, language, max_qc_calls, preferences)."""
    uploaded_file = st.file_uploader(
        "Upload a book",
        type=["epub", "html", "htm", "md", "markdown"],
        label_visibility="collapsed",
    )

    col1, col2 = st.columns(2)
    with col1:
        num_cards = st.slider("Number of cards", 5, 80, 15)
        model = st.selectbox("Model", ["haiku", "sonnet", "opus"], index=0)
        max_qc_calls = st.slider(
            "Quality review rounds",
            1,
            5,
            3,
            help="How many times the AI reviews and improves the cards before finishing.",
        )
    with col2:
        card_size = st.selectbox(
            "Card size",
            ["A6", "A5"],
            index=0,
            help="A6 → 4 cards per A4 sheet · A5 → 2 cards per A4 sheet",
        )
        language = st.text_input("Language (optional)", placeholder="e.g. English, Spanish")

    user_preferences = st.text_area(
        "Preferences (optional)",
        placeholder="Any instructions for the agent…",
        height=80,
    )

    return (
        uploaded_file,
        num_cards,
        card_size or "A6",
        model or "haiku",
        language or None,
        max_qc_calls,
        user_preferences,
    )


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> None:
    _init_state()
    _sidebar()

    st.title("📚 Breaking Books")
    st.markdown(
        "Welcome! This tool turns any non-fiction book into a collaborative, hands-on learning game."
    )

    # --- Handle follow-up instructions ---
    pending = st.session_state.get("pending_instructions")
    if pending and st.session_state["agent_done"]:
        st.session_state["pending_instructions"] = None
        config: Config = st.session_state["config"]
        work_dir: WorkDir = st.session_state["work_dir"]
        out_dir: OutDir = st.session_state["out_dir"]

        for old_pdf in work_dir.renders_dir.glob("card-*.pdf"):
            old_pdf.unlink()

        # Show previous run log collapsed
        prev_summary = _result_summary(st.session_state["messages"])
        with st.status(f"Previous run — {prev_summary}", state="complete", expanded=False):
            render_agent_log(st.session_state["messages"])
        _maybe_log_download(st.session_state["messages"], key="prev_run")

        st.chat_message("user").markdown(pending)

        new_msgs = _stream_agent(
            st.session_state["book_html"],
            config,
            work_dir,
            out_dir,
            resume=True,
            instructions=pending,
        )
        st.session_state["messages"].extend(new_msgs)
        _maybe_log_download(st.session_state["messages"], key="follow_up")

        _show_results(work_dir, out_dir, config, new_version=True)

        if follow_up := st.chat_input("Follow-up instructions…"):
            st.session_state["pending_instructions"] = follow_up
            st.rerun()
        return

    # --- Config (only shown before generation starts) ---
    if not st.session_state["generation_started"]:
        uploaded_file, num_cards, card_size, model, language, max_qc_calls, user_preferences = (
            _config_section()
        )

        if st.button(
            "Generate deck",
            type="primary",
            use_container_width=True,
            disabled=uploaded_file is None,
        ):
            # Save file to a temp path that survives the rerun
            suffix = Path(uploaded_file.name).suffix
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp_file.write(uploaded_file.read())
            tmp_file.close()

            st.session_state["_pending_file_path"] = Path(tmp_file.name)
            st.session_state["_pending_config"] = {
                "num_cards": num_cards,
                "card_size": card_size,
                "model": model,
                "language": language,
                "max_qc_calls": max_qc_calls,
                "user_preferences": user_preferences,
            }
            st.session_state["generation_started"] = True
            st.session_state["messages"] = []
            st.session_state["agent_done"] = False
            st.rerun()  # hides config, then runs agent on the next render
        return

    # --- Run agent (first rerun after Generate is clicked, before messages exist) ---
    if not st.session_state["messages"] and not st.session_state["agent_done"]:
        pending_file: Path = st.session_state["_pending_file_path"]
        pending_cfg: dict = st.session_state["_pending_config"]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = random.randint(1000, 9999)
        slug = slugify(pending_file.stem) or "output"
        output_dir = Path("output") / f"{timestamp}_{random_suffix}_{slug}"

        config = Config(**pending_cfg)
        work_dir = WorkDir.create(output_dir / "tmp")
        out_dir = OutDir.create(output_dir / "out")

        st.session_state["config"] = config
        st.session_state["work_dir"] = work_dir
        st.session_state["out_dir"] = out_dir

        with st.spinner("Loading book…"):
            book_html = load_book(pending_file)
            out_dir.book_html_path.write_text(book_html, encoding="utf-8")
            st.session_state["book_html"] = book_html

        new_msgs = _stream_agent(book_html, config, work_dir, out_dir)
        st.session_state["messages"] = new_msgs
        st.session_state["agent_done"] = True
        _maybe_log_download(new_msgs, key="first_run")

        _show_results(work_dir, out_dir, config)

        if follow_up := st.chat_input("Follow-up instructions…"):
            st.session_state["pending_instructions"] = follow_up
            st.rerun()
        return

    # --- Replay stored messages on page rerun ---
    if st.session_state["messages"]:
        prev_summary = _result_summary(st.session_state["messages"])
        with st.status(
            f"Agent log — {prev_summary}",
            state="complete",
            expanded=False,
        ):
            render_agent_log(st.session_state["messages"])
        _maybe_log_download(st.session_state["messages"], key="replay")

        if st.session_state["agent_done"]:
            _show_results(
                st.session_state["work_dir"],
                st.session_state["out_dir"],
                st.session_state["config"],
            )
            if follow_up := st.chat_input("Follow-up instructions…"):
                st.session_state["pending_instructions"] = follow_up
                st.rerun()


main()
