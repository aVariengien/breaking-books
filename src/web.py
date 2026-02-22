"""Streamlit UI for Breaking Books v2."""

import asyncio
import json
import random
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from slugify import slugify

from agent import run_agent
from lib import log
from lib.models import BBGame, Config, OutDir, WorkDir
from tools.extract_book_content import load_book
from tools.merge_pdfs import merge_pdfs_to_print
from tools.render_template import cards_json_to_pdfs

# ------------------------------------------------------------------
# Session state defaults
# ------------------------------------------------------------------

_DEFAULTS: dict[str, Any] = {
    "uploaded_path": None,
    "book_html": None,
    "config": None,
    "work_dir": None,
    "out_dir": None,
    "output_dir": None,
    "messages": [],
    "agent_done": False,
    "pending_instructions": None,
}


def _init_state() -> None:
    for key, default in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


# ------------------------------------------------------------------
# Message serialization / display
# ------------------------------------------------------------------


def _serialize_message(message: Any) -> dict:
    """Convert an SDK message to a JSON-serializable dict for session_state storage."""
    if isinstance(message, AssistantMessage):
        blocks = []
        for block in message.content:
            if isinstance(block, TextBlock):
                blocks.append({"type": "text", "text": block.text})
            elif isinstance(block, ThinkingBlock):
                blocks.append({"type": "thinking", "thinking": block.thinking})
            elif isinstance(block, ToolUseBlock):
                blocks.append(
                    {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
                )
            elif isinstance(block, ToolResultBlock):
                content = block.content
                if isinstance(content, list):
                    content = "\n".join(
                        c.get("text", repr(c)) if isinstance(c, dict) else repr(c) for c in content
                    )
                blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.tool_use_id,
                        "content": str(content or ""),
                        "is_error": block.is_error or False,
                    }
                )
        return {"kind": "assistant", "blocks": blocks}
    elif isinstance(message, ResultMessage):
        return {
            "kind": "result",
            "num_turns": message.num_turns,
            "total_cost_usd": message.total_cost_usd,
            "session_id": message.session_id,
            "is_error": message.is_error,
            "duration_ms": message.duration_ms,
        }
    elif isinstance(message, UserMessage):
        content = message.content if isinstance(message.content, str) else repr(message.content)
        return {"kind": "user", "content": content}
    elif isinstance(message, SystemMessage):
        return {"kind": "system", "subtype": message.subtype}
    return {"kind": "unknown", "repr": repr(message)}


def _render_message(msg: dict) -> None:
    """Render a serialized message dict using Streamlit widgets."""
    kind = msg.get("kind")
    if kind == "assistant":
        for block in msg.get("blocks", []):
            _render_block(block)
    elif kind == "result":
        cost = f"${msg['total_cost_usd']:.4f}" if msg.get("total_cost_usd") else "N/A"
        duration_s = msg.get("duration_ms", 0) / 1000
        if msg.get("is_error"):
            st.error(
                f"Agent finished with error — {msg['num_turns']} turns, {cost}, {duration_s:.1f}s"
            )
        else:
            st.success(f"Agent done — {msg['num_turns']} turns, {cost}, {duration_s:.1f}s")
    elif kind == "user":
        st.chat_message("user").markdown(msg.get("content", ""))
    # Skip system and unknown messages


def _render_block(block: dict) -> None:
    """Render a single content block."""
    btype = block.get("type")
    if btype == "text":
        text = block.get("text", "").strip()
        if text:
            st.markdown(text)
    elif btype == "thinking":
        with st.expander("Thinking", expanded=False):
            st.text(block.get("thinking", ""))
    elif btype == "tool_use":
        name = block.get("name", "tool")
        tool_input = block.get("input", {})
        label = _tool_label(name, tool_input)
        with st.status(label, state="complete"):
            # Show truncated input for readability
            input_str = json.dumps(tool_input, indent=2, ensure_ascii=False)
            if len(input_str) > 2000:
                input_str = input_str[:2000] + "\n..."
            st.code(input_str, language="json")
    elif btype == "tool_result":
        content = block.get("content", "")
        if block.get("is_error"):
            st.error(content[:1000] if len(content) > 1000 else content)
        elif content.strip():
            # Show tool results compactly
            display = content[:1000] + "..." if len(content) > 1000 else content
            st.caption(display)


def _tool_label(name: str, tool_input: dict) -> str:
    """Build a human-readable label for a tool use status widget."""
    if name == "Write":
        return f"Write → {tool_input.get('file_path', '?')}"
    if name == "Edit":
        return f"Edit → {tool_input.get('file_path', '?')}"
    if name == "Read":
        return f"Read → {tool_input.get('file_path', '?')}"
    if name == "Glob":
        return f"Glob → {tool_input.get('pattern', '?')}"
    if name == "mcp__bb__quality_control":
        return "Quality Control"
    return f"Tool: {name}"


# ------------------------------------------------------------------
# Agent streaming
# ------------------------------------------------------------------


def _stream_agent(
    book_html: str,
    config: Config,
    work_dir: WorkDir,
    out_dir: OutDir,
    *,
    resume: bool = False,
    instructions: str = "",
) -> list[dict]:
    """Run the agent synchronously, streaming messages to the Streamlit UI.

    Returns the list of serialized messages produced during this run.
    """
    container = st.container()
    new_messages: list[dict] = []

    async def _run() -> None:
        async for message in run_agent(
            book_html, config, work_dir, out_dir, resume=resume, instructions=instructions
        ):
            log.log_message(message)
            serialized = _serialize_message(message)
            new_messages.append(serialized)
            with container:
                _render_message(serialized)

    asyncio.run(_run())
    return new_messages


# ------------------------------------------------------------------
# Results display
# ------------------------------------------------------------------


def _show_results(work_dir: WorkDir, out_dir: OutDir, config: Config, output_dir: Path) -> None:
    """Load BBGame from cards.json and display the deck + QC reports."""
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
    st.subheader(f"Deck — {len(game.cards)} cards")

    # Render PDFs if not already done
    renders_dir = work_dir.renders_dir
    pdf_paths = sorted(renders_dir.glob("card-*.pdf"))
    if not pdf_paths and game.cards:
        with st.spinner("Rendering cards to PDF..."):
            pdf_paths = cards_json_to_pdfs(
                cards_path, renders_dir, config, out_dir.images_dir, n_jobs=1
            )

    # Card gallery
    if pdf_paths:
        cols = st.columns(min(len(pdf_paths), 4))
        for i, pdf_path in enumerate(pdf_paths):
            with cols[i % len(cols)]:
                st.caption(f"Card {i}")
                # Show PDF as download since Streamlit can't inline PDFs easily
                st.download_button(
                    f"card-{i}.pdf",
                    pdf_path.read_bytes(),
                    file_name=f"card-{i}.pdf",
                    mime="application/pdf",
                    key=f"dl_card_{i}",
                )

    # Merge into deck.pdf
    deck_path = output_dir / "deck.pdf"
    if pdf_paths and not deck_path.exists():
        with st.spinner("Merging into printable deck..."):
            merge_pdfs_to_print(pdf_paths, deck_path)

    if deck_path.exists():
        st.download_button(
            "Download deck.pdf",
            deck_path.read_bytes(),
            file_name="deck.pdf",
            mime="application/pdf",
            key="dl_deck",
        )

    # QC reports
    qc_reports = sorted(out_dir.root.glob("qc-report-v*.md"))
    if qc_reports:
        with st.expander(f"QC Reports ({len(qc_reports)})", expanded=False):
            for report_path in reversed(qc_reports):
                st.markdown(f"**{report_path.name}**")
                st.markdown(report_path.read_text(encoding="utf-8"))
                st.divider()

    # cards.json download
    st.download_button(
        "Download cards.json",
        cards_path.read_bytes(),
        file_name="cards.json",
        mime="application/json",
        key="dl_cards_json",
    )


# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------


def _sidebar() -> tuple[Any, int, str, str | None, int, str]:
    """Render sidebar config widgets. Returns (uploaded_file, num_cards, card_size, language, max_qc_calls, user_preferences)."""
    with st.sidebar:
        st.title("Breaking Books")
        uploaded_file = st.file_uploader(
            "Book file", type=["epub", "html", "htm", "md", "markdown"]
        )
        num_cards = st.slider("Number of cards", 5, 80, 15)
        card_size = st.selectbox("Card size", ["A6", "A5"], index=0)
        language = st.text_input("Language (optional)", placeholder="e.g. English, Spanish")
        max_qc_calls = st.slider("Max QC iterations", 1, 5, 3)
        user_preferences = st.text_area(
            "Preferences", placeholder="Any instructions for the agent..."
        )
    return (
        uploaded_file,
        num_cards,
        card_size or "A6",
        language or None,
        max_qc_calls,
        user_preferences,
    )


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> None:
    """Entry point. Sidebar config + main area for agent output and results."""
    st.set_page_config(page_title="Breaking Books", layout="wide")
    _init_state()

    uploaded_file, num_cards, card_size, language, max_qc_calls, user_preferences = _sidebar()

    # --- Handle follow-up instructions from chat_input ---
    pending = st.session_state.get("pending_instructions")
    if pending and st.session_state["agent_done"]:
        st.session_state["pending_instructions"] = None
        config: Config = st.session_state["config"]
        work_dir: WorkDir = st.session_state["work_dir"]
        out_dir: OutDir = st.session_state["out_dir"]
        log.setup(out_dir.log_path)

        # Clear old renders so they get regenerated
        for old_pdf in work_dir.renders_dir.glob("card-*.pdf"):
            old_pdf.unlink()

        # Replay previous messages
        for msg in st.session_state["messages"]:
            _render_message(msg)

        # Show the follow-up as a user message
        st.chat_message("user").markdown(pending)

        # Stream the resumed agent
        new_msgs = _stream_agent(
            st.session_state["book_html"],
            config,
            work_dir,
            out_dir,
            resume=True,
            instructions=pending,
        )
        st.session_state["messages"].extend(new_msgs)

        # Show updated results
        _show_results(work_dir, out_dir, config, st.session_state["output_dir"])

        # Chat input for further follow-ups
        if follow_up := st.chat_input("Follow-up instructions..."):
            st.session_state["pending_instructions"] = follow_up
            st.rerun()
        return

    # --- "Create" button flow ---
    create_clicked = st.sidebar.button("Create", type="primary", disabled=uploaded_file is None)

    if create_clicked and uploaded_file is not None:
        # Save uploaded file to disk
        suffix = Path(uploaded_file.name).suffix
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_file.write(uploaded_file.read())
        tmp_file.close()
        uploaded_path = Path(tmp_file.name)
        st.session_state["uploaded_path"] = uploaded_path

        # Create output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = random.randint(1000, 9999)
        slug = slugify(Path(uploaded_file.name).stem) or "output"
        output_dir = Path("output") / f"{timestamp}_{random_suffix}_{slug}"

        config = Config(
            num_cards=num_cards,
            card_size=card_size,  # type: ignore[arg-type]
            language=language,
            max_qc_calls=max_qc_calls,
            user_preferences=user_preferences,
        )
        work_dir = WorkDir.create(output_dir / "tmp")
        out_dir = OutDir.create(output_dir / "out")
        log.setup(out_dir.log_path)

        # Store in session state
        st.session_state["config"] = config
        st.session_state["work_dir"] = work_dir
        st.session_state["out_dir"] = out_dir
        st.session_state["output_dir"] = output_dir
        st.session_state["messages"] = []
        st.session_state["agent_done"] = False

        # Load book
        with st.spinner("Loading book..."):
            book_html = load_book(uploaded_path)
            out_dir.book_html_path.write_text(book_html, encoding="utf-8")
            st.session_state["book_html"] = book_html

        # Stream agent
        new_msgs = _stream_agent(book_html, config, work_dir, out_dir)
        st.session_state["messages"] = new_msgs
        st.session_state["agent_done"] = True

        # Show results
        _show_results(work_dir, out_dir, config, output_dir)

        # Chat input for follow-up
        if follow_up := st.chat_input("Follow-up instructions..."):
            st.session_state["pending_instructions"] = follow_up
            st.rerun()
        return

    # --- Replay stored messages on rerun (no agent running) ---
    if st.session_state["messages"]:
        for msg in st.session_state["messages"]:
            _render_message(msg)

        if st.session_state["agent_done"]:
            _show_results(
                st.session_state["work_dir"],
                st.session_state["out_dir"],
                st.session_state["config"],
                st.session_state["output_dir"],
            )
            if follow_up := st.chat_input("Follow-up instructions..."):
                st.session_state["pending_instructions"] = follow_up
                st.rerun()
    else:
        st.info("Upload a book file and click **Create** to generate a flashcard deck.")


if __name__ == "__main__":
    main()
