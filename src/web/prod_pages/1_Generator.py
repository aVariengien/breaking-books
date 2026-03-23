"""Streamlit UI for Breaking Books v2."""

import asyncio
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

_FREE_MODELS = ["gemini/gemini-3.1-flash-lite-preview"]
_ADMIN_MODELS = [
    "gemini/gemini-3.1-flash-lite-preview",
    "gemini/gemini-3.1-pro-preview",
    "anthropic/claude-sonnet-4-6",
]

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
    "admin_unlocked": False,
}


def _init_state() -> None:
    for key, default in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


# ------------------------------------------------------------------
# Event serialization (ADK Events → JSON-serializable dicts)
# ------------------------------------------------------------------


def _serialize_event(event: Any) -> list[dict]:
    """Convert one ADK Event into one or more JSON-serializable dicts.

    Returns a list because one Event can carry multiple pieces (e.g. a tool
    call AND a tool result in separate events — but we produce one dict per
    logical item so the UI can render them in order).
    """
    items: list[dict] = []
    author = getattr(event, "author", None) or "?"
    content = getattr(event, "content", None)
    partial = bool(getattr(event, "partial", False))

    if author == "user":
        text = ""
        if content and content.parts:
            text = " ".join(getattr(p, "text", "") or "" for p in content.parts).strip()
        if text:
            items.append({"__type__": "user", "text": text})
        return items

    # Always extract thought parts first — they can accompany tool calls too.
    # Skip partial=True thought chunks: they're streaming fragments; only emit
    # the final complete thought so the UI gets one clean expander per thought.
    if content and content.parts:
        thought_text = " ".join(
            getattr(p, "text", "") or ""
            for p in content.parts
            if getattr(p, "thought", False)
        ).strip()
        if thought_text and not partial:
            items.append({"__type__": "thought", "text": thought_text})

    fn_calls = _safe_fn_calls(event)
    fn_responses = _safe_fn_responses(event)

    for fc in fn_calls:
        items.append(
            {
                "__type__": "tool_call",
                "call_id": getattr(fc, "id", ""),
                "name": getattr(fc, "name", ""),
                "args": dict(getattr(fc, "args", {}) or {}),
            }
        )

    for fr in fn_responses:
        name = getattr(fr, "name", "")
        response = getattr(fr, "response", {}) or {}
        content_val = response.get("result", "")
        if not isinstance(content_val, str):
            content_val = json.dumps(content_val, ensure_ascii=False, default=str)
        items.append(
            {
                "__type__": "tool_result",
                "name": name,
                "content": content_val,
                "is_error": "Error" in content_val[:20] if content_val else False,
            }
        )

    if content and content.parts and not fn_calls and not fn_responses:
        plain_text = " ".join(
            getattr(p, "text", "") or ""
            for p in content.parts
            if not getattr(p, "thought", False)
        ).strip()
        if plain_text:
            items.append({"__type__": "text", "text": plain_text, "partial": partial})

    return items


def _safe_fn_calls(event: Any) -> list:
    try:
        r = event.get_function_calls()
        return r if r else []
    except Exception:
        return []


def _safe_fn_responses(event: Any) -> list:
    try:
        r = event.get_function_responses()
        return r if r else []
    except Exception:
        return []


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


def _result_summary(events: list[dict]) -> str:
    """Build a brief summary string from the event list."""
    done = next((e for e in reversed(events) if e.get("__type__") == "done"), None)
    parts = []
    if done and done.get("turns"):
        turns = done["turns"]
        parts.append(f"{turns} turn{'s' if turns != 1 else ''}")
    if done and done.get("elapsed_s") is not None:
        elapsed_s = int(done["elapsed_s"])
        mins, secs = divmod(elapsed_s, 60)
        parts.append(f"{mins}m {secs}s" if mins else f"{secs}s")
    if not parts:
        tool_calls = sum(1 for e in events if e.get("__type__") == "tool_call")
        parts.append(f"{tool_calls} tool calls" if tool_calls else "completed")
    return " · ".join(parts)


def _stream_agent(
    book_html: str,
    config: Config,
    work_dir: WorkDir,
    out_dir: OutDir,
    *,
    resume: bool = False,
    instructions: str = "",
) -> list[dict]:
    """Run the agent, streaming all events inside a single st.status() container."""
    new_events: list[dict] = []
    start_t = time.monotonic()
    last_action_t: list[float] = [start_t]
    turn_count: list[int] = [0]
    had_error: list[bool] = [False]
    non_cached_prompt_tokens: list[int] = [0]
    cached_prompt_tokens: list[int] = [0]
    output_tokens: list[int] = [0]
    thought_tokens: list[int] = [0]

    with st.status(
        "Resuming…" if resume else "Generating your deck…",
        expanded=True,
    ) as status:

        async def _run() -> None:
            async for event in run_agent(
                book_html, config, work_dir, out_dir, resume=resume, instructions=instructions
            ):
                log.log_message(event)

                # Accumulate token usage from each model response event.
                usage = getattr(event, "usage_metadata", None)
                if usage:
                    print(f"usage_metadata: {usage!r}")
                    cached = getattr(usage, "cached_content_token_count", 0) or 0
                    prompt_total = getattr(usage, "prompt_token_count", 0) or 0
                    candidates = getattr(usage, "candidates_token_count", 0) or 0
                    thoughts = getattr(usage, "thoughts_token_count", 0) or 0
                    non_cached_prompt_tokens[0] += prompt_total - cached
                    cached_prompt_tokens[0] += cached
                    output_tokens[0] += candidates + thoughts
                    thought_tokens[0] += thoughts

                serialized_items = _serialize_event(event)
                for item in serialized_items:
                    new_events.append(item)
                    elapsed = time.monotonic() - last_action_t[0]
                    update_status_for_message(status, item, elapsed=elapsed)
                    last_action_t[0] = time.monotonic()
                    render_message(item)

                # Count turn completions via is_final_response
                try:
                    if event.is_final_response():
                        turn_count[0] += 1
                except Exception:
                    pass

        try:
            asyncio.run(_run())
        except Exception as exc:
            had_error[0] = True
            st.error(f"Agent error: {exc}")

        elapsed_s = time.monotonic() - start_t
        from web.utils import _estimate_cost

        estimated_cost_usd = _estimate_cost(
            config.model,
            non_cached_prompt_tokens[0],
            cached_prompt_tokens[0],
            output_tokens[0],
        )
        done_event = {
            "__type__": "done",
            "turns": turn_count[0],
            "elapsed_s": round(elapsed_s, 1),
            "non_cached_prompt_tokens": non_cached_prompt_tokens[0],
            "cached_prompt_tokens": cached_prompt_tokens[0],
            "output_tokens": output_tokens[0],
            "thought_tokens": thought_tokens[0],
            "model": config.model,
            **({"estimated_cost_usd": round(estimated_cost_usd, 6)} if estimated_cost_usd is not None else {}),
        }
        new_events.append(done_event)
        render_message(done_event)

        summary = _result_summary(new_events)
        is_error = had_error[0]
        status.update(
            label=f"Generation failed — {summary}" if is_error else f"Agent log — {summary}",
            state="error" if is_error else "complete",
            expanded=False,
        )

    return new_events


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
# Admin dialog
# ------------------------------------------------------------------


@st.dialog("Admin Access")
def _admin_dialog() -> None:
    if st.session_state.get("admin_unlocked"):
        st.success("Admin access is already unlocked.")
        return
    try:
        admin_pw: str = st.secrets["admin_password"]
    except (KeyError, FileNotFoundError):
        st.warning("No admin password is configured in `.streamlit/secrets.toml`.")
        return
    entered = st.text_input("Password", type="password", key="_admin_pw_input")
    if st.button("Unlock", type="primary", key="_admin_pw_submit", use_container_width=True):
        if entered == admin_pw:
            st.session_state["admin_unlocked"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")


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

        # Admin lock/unlock button — always at the very bottom of the sidebar
        st.divider()
        admin = st.session_state.get("admin_unlocked", False)
        icon = "🔓 Admin unlocked" if admin else "🔒 Admin"
        if st.button(icon, use_container_width=True, key="_admin_btn"):
            _admin_dialog()


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

    admin = st.session_state.get("admin_unlocked", False)

    col1, col2 = st.columns(2)
    with col1:
        num_cards = st.slider("Number of cards", 5, 80, 35)
        if admin:
            model = st.selectbox(
                "Model",
                _ADMIN_MODELS,
                index=0,
                key="_model_admin_sel",
            ) or _ADMIN_MODELS[0]
        else:
            st.selectbox(
                "Model",
                _FREE_MODELS,
                index=0,
                disabled=True,
                help="Unlock admin access to use advanced models.",
                key="_model_locked_sel",
            )
            model = _FREE_MODELS[0]
        max_qc_calls = st.slider(
            "Quality review rounds",
            1,
            5,
            1,
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
        model or _FREE_MODELS[0],
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
