"""Streamlit UI for Breaking Books v2."""

import asyncio
import json
import random
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer
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
            input_str = json.dumps(tool_input, indent=2, ensure_ascii=False)
            if len(input_str) > 2000:
                input_str = input_str[:2000] + "\n..."
            st.code(input_str, language="json")
    elif btype == "tool_result":
        content = block.get("content", "")
        if block.get("is_error"):
            st.error(content[:1000] if len(content) > 1000 else content)
        elif content.strip():
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
    st.info(
        "Agent resuming…"
        if resume
        else "Agent running… this may take a few minutes. Do not refresh the page."
    )
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
    """Load BBGame from cards.json and display the deck + QC reports.

    new_version=True: re-render card PDFs and save a new deck-vNNN.pdf.
    new_version=False: use whatever already exists; render only if nothing is there yet.
    """
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
    if card_types:
        st.caption("  ".join(f"`{t}` ×{n}" for t, n in sorted(card_types.items())))

    # Render card PDFs when needed
    renders_dir = work_dir.renders_dir
    existing_card_pdfs = sorted(renders_dir.glob("card-*.pdf"))
    if (not existing_card_pdfs or new_version) and game.cards:
        with st.spinner("Rendering cards to PDF…"):
            existing_card_pdfs = cards_json_to_pdfs(
                cards_path, renders_dir, config, out_dir.images_dir, n_jobs=1
            )

    # Build a new versioned deck if needed
    versions = _deck_versions(out_dir)
    if existing_card_pdfs and (not versions or new_version):
        deck_path = _next_deck_path(out_dir)
        with st.spinner(f"Building {deck_path.name}…"):
            merge_pdfs_to_print(existing_card_pdfs, deck_path)
        versions = _deck_versions(out_dir)

    # cards.json download (always available)
    st.download_button(
        "⬇ Download cards.json",
        cards_path.read_bytes(),
        file_name="cards.json",
        mime="application/json",
        key="dl_cards_json",
    )

    # Version selector + inline viewer
    if versions:
        # Newest first; label the latest one
        options = list(reversed(versions))
        labels = [f"{p.name} (latest)" if i == 0 else p.name for i, p in enumerate(options)]
        label_to_path = dict(zip(labels, options))

        selected_label = st.selectbox("Deck version", labels, index=0)
        selected_path = label_to_path[selected_label]

        dl_col, _ = st.columns([1, 3])
        with dl_col:
            st.download_button(
                f"⬇ Download {selected_path.name}",
                selected_path.read_bytes(),
                file_name=selected_path.name,
                mime="application/pdf",
                key=f"dl_{selected_path.name}",
            )

        pdf_viewer(str(selected_path), annotations=[])

    # QC reports
    qc_reports = sorted(out_dir.root.glob("qc-report-v*.md"))
    if qc_reports:
        with st.expander(f"QC Reports ({len(qc_reports)})", expanded=False):
            for report_path in reversed(qc_reports):
                st.markdown(f"**{report_path.name}**")
                st.markdown(report_path.read_text(encoding="utf-8"))
                st.divider()


# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------


def _sidebar() -> tuple[Any, int, str, str, str | None, int, str]:
    """Render sidebar config widgets."""
    with st.sidebar:
        st.title("Breaking Books")
        uploaded_file = st.file_uploader(
            "Book file", type=["epub", "html", "htm", "md", "markdown"]
        )
        num_cards = st.slider("Number of cards", 5, 80, 15)
        card_size = st.selectbox("Card size", ["A6", "A5"], index=0)
        model = st.selectbox("Model", ["haiku", "sonnet", "opus"], index=0)
        language = st.text_input("Language (optional)", placeholder="e.g. English, Spanish")
        max_qc_calls = st.slider("Max QC iterations", 1, 5, 3)
        user_preferences = st.text_area(
            "Preferences", placeholder="Any instructions for the agent..."
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
    """Entry point. Sidebar config + main area for agent output and results."""
    st.set_page_config(page_title="Breaking Books", layout="wide")
    _init_state()

    uploaded_file, num_cards, card_size, model, language, max_qc_calls, user_preferences = (
        _sidebar()
    )

    # --- Handle follow-up instructions from chat_input ---
    pending = st.session_state.get("pending_instructions")
    if pending and st.session_state["agent_done"]:
        st.session_state["pending_instructions"] = None
        config: Config = st.session_state["config"]
        work_dir: WorkDir = st.session_state["work_dir"]
        out_dir: OutDir = st.session_state["out_dir"]
        log.setup(out_dir.log_path)

        # Clear stale card renders so they get regenerated from the updated cards.
        # Versioned deck PDFs in out_dir are kept.
        for old_pdf in work_dir.renders_dir.glob("card-*.pdf"):
            old_pdf.unlink()

        # Replay previous messages
        for msg in st.session_state["messages"]:
            _render_message(msg)

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

        _show_results(work_dir, out_dir, config, new_version=True)

        if follow_up := st.chat_input("Follow-up instructions..."):
            st.session_state["pending_instructions"] = follow_up
            st.rerun()
        return

    # --- "Create" button flow ---
    create_clicked = st.sidebar.button("Create", type="primary", disabled=uploaded_file is None)

    if create_clicked and uploaded_file is not None:
        suffix = Path(uploaded_file.name).suffix
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_file.write(uploaded_file.read())
        tmp_file.close()
        st.session_state["uploaded_path"] = Path(tmp_file.name)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = random.randint(1000, 9999)
        slug = slugify(Path(uploaded_file.name).stem) or "output"
        output_dir = Path("output") / f"{timestamp}_{random_suffix}_{slug}"

        config = Config(
            num_cards=num_cards,
            card_size=card_size,  # type: ignore[arg-type]
            model=model,  # type: ignore[arg-type]
            language=language,
            max_qc_calls=max_qc_calls,
            user_preferences=user_preferences,
        )
        work_dir = WorkDir.create(output_dir / "tmp")
        out_dir = OutDir.create(output_dir / "out")
        log.setup(out_dir.log_path)

        st.session_state["config"] = config
        st.session_state["work_dir"] = work_dir
        st.session_state["out_dir"] = out_dir
        st.session_state["messages"] = []
        st.session_state["agent_done"] = False

        with st.spinner("Loading book..."):
            book_html = load_book(st.session_state["uploaded_path"])
            out_dir.book_html_path.write_text(book_html, encoding="utf-8")
            st.session_state["book_html"] = book_html

        new_msgs = _stream_agent(book_html, config, work_dir, out_dir)
        st.session_state["messages"] = new_msgs
        st.session_state["agent_done"] = True

        _show_results(work_dir, out_dir, config)

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
            )
            if follow_up := st.chat_input("Follow-up instructions..."):
                st.session_state["pending_instructions"] = follow_up
                st.rerun()
    else:
        st.info("Upload a book file and click **Create** to generate a flashcard deck.")


if __name__ == "__main__":
    main()
