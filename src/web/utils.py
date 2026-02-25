"""Shared utilities and reusable UI components for the Breaking Books web app."""

import difflib
import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Literal

import streamlit as st
from streamlit_pdf_viewer import pdf_viewer

from lib.constants import IMAGE_CACHE_DIR, RUNWARE_MODEL
from tools.merge_pdfs import merge_pdfs_to_print
from tools.pdf_to_pngs import pdf_to_pngs
from tools.render_template import cards_json_to_pdfs


# ---------------------------------------------------------------------------
# Agent log rendering
# ---------------------------------------------------------------------------


def tool_label_plain(name: str, tool_input: dict) -> str:
    """Label without emoji, suitable for the st.status() header."""
    if name == "Write":
        return f"Write {Path(tool_input.get('file_path', '?')).name}"
    if name == "Edit":
        return f"Edit {Path(tool_input.get('file_path', '?')).name}"
    if name == "Read":
        return f"Read {Path(tool_input.get('file_path', '?')).name}"
    if name == "Glob":
        return f"Glob {tool_input.get('pattern', '?')}"
    if name == "mcp__bb__quality_control":
        return "Quality Control"
    return name


def _tool_label(name: str, tool_input: dict) -> str:
    if name == "Write":
        return f"✏️ Write → {Path(tool_input.get('file_path', '?')).name}"
    if name == "Edit":
        return f"✏️ Edit → {Path(tool_input.get('file_path', '?')).name}"
    if name == "Read":
        return f"📖 Read → {Path(tool_input.get('file_path', '?')).name}"
    if name == "Glob":
        return f"🔍 Glob → {tool_input.get('pattern', '?')}"
    if name == "mcp__bb__quality_control":
        return "✅ Quality Control"
    return f"🔧 {name}"


def update_status_for_message(status: Any, msg: dict, *, elapsed: float | None = None) -> None:
    """Update a st.status() label to reflect the current message.

    Pass ``elapsed`` (seconds since the last update) to include timing in labels,
    e.g. "Thought 3s → Write cards.json". Without it, plain labels are used.
    """
    mtype = msg.get("__type__")
    if mtype == "AssistantMessage":
        for block in msg.get("content", []):
            btype = block.get("__type__")
            if btype == "ThinkingBlock":
                label = f"Thinking… ({elapsed:.0f}s)" if elapsed is not None else "Thinking…"
                status.update(label=label)
            elif btype == "ToolUseBlock":
                plain = tool_label_plain(block.get("name", ""), block.get("input", {}))
                label = f"Thought {elapsed:.0f}s → {plain}" if elapsed is not None else f"→ {plain}"
                status.update(label=label)
            elif btype == "ToolResultBlock":
                label = (
                    f"Tool returned ({elapsed:.0f}s)" if elapsed is not None else "Tool returned"
                )
                status.update(label=label)
            elif btype == "TextBlock":
                status.update(label="Writing…")
    elif mtype == "SystemMessage":
        status.update(label="Starting…")


def _render_edit_diff(tool_input: dict) -> None:
    """Render an Edit tool input as a unified diff."""
    old = tool_input.get("old_string", "")
    new = tool_input.get("new_string", "")
    name = Path(tool_input.get("file_path", "?")).name
    diff_lines = list(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{name}",
            tofile=f"b/{name}",
            n=3,
        )
    )[3:]  # Drop the header lines
    if diff_lines:
        diff_lines = [line.rstrip() for line in diff_lines]
        st.code("\n".join(diff_lines), language="diff")
    else:
        st.caption("(no changes)")


def _render_tool_result_content(content: str, tool_name: str | None) -> None:
    """Render tool result content using the appropriate display format for the tool."""
    if tool_name == "mcp__bb__quality_control":
        with st.expander("📝 Quality Control output", expanded=True):
            st.markdown(content)
    elif tool_name in ("Edit", "Write"):
        # When successfull, the content just says so. Not useful.
        pass
    # elif tool_name in ("Write", ):
    #     #
    #     with st.expander(f"📝 {tool_name} successful", expanded=False):
    #         st.markdown(content)
    else:
        with st.expander(f"📖 {tool_name} output", expanded=False):
            st.code(content, language=None)


def _render_block(block: dict, tool_names: dict[str, str] | None = None) -> None:
    btype = block.get("__type__")
    if btype == "TextBlock":
        text = block.get("text", "").strip()
        if text:
            st.markdown(text)
    elif btype == "ThinkingBlock":
        thinking = block.get("thinking", "")
        length = len(thinking.strip())
        if length < 1000 and "\n" not in thinking.strip():
            st.caption(f"Thinking: {thinking}")
        else:
            with st.expander(f"Thinking ({length} characters)", expanded=False):
                st.markdown(thinking)
    elif btype == "ToolUseBlock":
        name = block.get("name", "tool")
        tool_input = block.get("input", {})
        expanded = name == "Edit"
        with st.expander(_tool_label(name, tool_input), expanded=expanded):
            if name == "Edit":
                _render_edit_diff(tool_input)
            else:
                st.code(json.dumps(tool_input, indent=2, ensure_ascii=False), language="json")
    elif btype == "ToolResultBlock":
        tool_use_id = block.get("tool_use_id", "")
        tool_name = (tool_names or {}).get(tool_use_id)
        content = block.get("content", "")
        if isinstance(content, list):
            content = "\n".join(
                c.get("text", repr(c)) if isinstance(c, dict) else repr(c) for c in content
            )
        content = str(content or "")
        if block.get("is_error"):
            st.error(content)
        elif content.strip():
            _render_tool_result_content(content, tool_name)
    else:
        st.write(f"Unknown block type: {btype}")
        st.code(json.dumps(block, indent=2, ensure_ascii=False), language="json")


def render_message(msg: dict, tool_names: dict[str, str] | None = None) -> None:
    """Render a single serialized agent SDK message."""
    mtype = msg.get("__type__")
    if mtype == "AssistantMessage":
        for block in msg.get("content", []):
            _render_block(block, tool_names)
    elif mtype == "ResultMessage":
        cost = f"${msg['total_cost_usd']:.4f}" if msg.get("total_cost_usd") else "N/A"
        duration_s = msg.get("duration_ms", 0) / 1000
        if msg.get("is_error"):
            st.error(
                f"Agent finished with error — {msg['num_turns']} turns · {cost} · {duration_s:.1f}s"
            )
        else:
            st.success(f"Done — {msg['num_turns']} turns · {cost} · {duration_s:.1f}s")
    elif mtype == "UserMessage":
        content = msg.get("content", "")
        if isinstance(content, list):
            for block in content:
                _render_block(block, tool_names)
        elif isinstance(content, str) and content.strip():
            st.chat_message("user").markdown(content)
    elif mtype == "SystemMessage":
        subtype = msg.get("subtype") or "init"
        st.info(f"System: {subtype}")


def build_tool_names(messages: list[dict]) -> dict[str, str]:
    """Build a tool_use_id → tool name mapping from a list of serialized messages."""
    tool_names: dict[str, str] = {}
    for msg in messages:
        if msg.get("__type__") == "AssistantMessage":
            for block in msg.get("content", []):
                if block.get("__type__") == "ToolUseBlock" and block.get("id"):
                    tool_names[block["id"]] = block.get("name", "")
    return tool_names


def render_agent_log(messages: list[dict]) -> None:
    """Render a list of serialized agent SDK messages."""
    tool_names = build_tool_names(messages)
    for msg in messages:
        render_message(msg, tool_names)


# ---------------------------------------------------------------------------
# Shared download-row + PDF viewer helper
# ---------------------------------------------------------------------------


def _download_row_and_viewer(
    pdf_bytes: bytes,
    pdf_filename: str,
    secondary: list[tuple[str, bytes, str, str]],  # (label, data, filename, mime)
    key_prefix: str,
) -> None:
    """Primary PDF download button (wide) + secondary buttons (narrow) + inline viewer."""
    if secondary:
        cols = st.columns([3] + [1] * len(secondary))
        pdf_col, *sec_cols = cols
    else:
        pdf_col = st.container()
        sec_cols = []

    with pdf_col:
        st.download_button(
            f"⬇ {pdf_filename}",
            data=pdf_bytes,
            file_name=pdf_filename,
            mime="application/pdf",
            type="primary",
            use_container_width=True,
            key=f"{key_prefix}_dl_primary",
        )

    for col, (label, data, fname, mime) in zip(sec_cols, secondary):
        with col:
            st.download_button(
                label,
                data=data,
                file_name=fname,
                mime=mime,
                use_container_width=True,
                key=f"{key_prefix}_dl_{fname}",
            )

    pdf_viewer(pdf_bytes, key=f"{key_prefix}_viewer")


# ---------------------------------------------------------------------------
# Render Deck component
# ---------------------------------------------------------------------------


def deck_viewer(
    versions: list[Path],
    *,
    cards_json_path: Path | None = None,
    card_pdfs: list[Path] | None = None,
    key_prefix: str = "deck",
) -> None:
    """
    Display versioned deck PDFs with a version selector, download buttons, and inline viewer.

    `versions` should be a list of deck PDF paths sorted oldest→newest.
    `cards_json_path` adds a secondary download button for the raw JSON.
    `card_pdfs` adds a card-images ZIP download (generated on demand, cached in session state).
    """
    if not versions:
        st.info("No deck available yet.")
        return

    # Newest first
    options = list(reversed(versions))
    labels = [f"{p.name} (latest)" if i == 0 else p.name for i, p in enumerate(options)]

    if len(options) > 1:
        selected_label = st.selectbox("Version", labels, index=0, key=f"{key_prefix}_version_sel")
        selected_path = dict(zip(labels, options))[selected_label]
    else:
        selected_path = options[0]

    # Build secondary button list
    secondary: list[tuple[str, bytes, str, str]] = []
    if cards_json_path and cards_json_path.exists():
        secondary.append(
            ("⬇ cards.json", cards_json_path.read_bytes(), "cards.json", "application/json")
        )

    zip_key = f"{key_prefix}_card_zip"
    if card_pdfs and zip_key in st.session_state:
        secondary.append(
            (
                "⬇ Card images",
                st.session_state[zip_key],
                "card-images.zip",
                "application/zip",
            )
        )

    _download_row_and_viewer(selected_path.read_bytes(), selected_path.name, secondary, key_prefix)

    # Card images ZIP generation button (shown until ZIP is ready)
    if card_pdfs and zip_key not in st.session_state:
        if st.button("Generate card images (ZIP)", key=f"{zip_key}_gen"):
            with st.spinner("Converting cards to images…"):
                st.session_state[zip_key] = make_card_images_zip(card_pdfs)
            st.rerun()


def make_card_images_zip(card_pdfs: list[Path], *, dpi: int = 150) -> bytes:
    """Convert a list of card PDFs to PNG images and return a ZIP archive."""
    with tempfile.TemporaryDirectory() as tmp:
        pairs = _card_pdfs_to_pngs(card_pdfs, Path(tmp) / "pngs", dpi=dpi)
        return _build_zip(pairs)


def render_deck_ui(
    cards_json_bytes: bytes,
    *,
    key_prefix: str = "deck",
) -> None:
    """
    Full render-deck UI component.

    Accepts a cards.json as raw bytes. Shows card-size selector immediately,
    then on "Render" renders all cards, merges to a printable PDF, displays it
    inline via pdf_viewer, and provides download buttons (PDF + card PNGs ZIP).

    `key_prefix` namespaces all widget keys for safe multi-instance embedding.
    """
    try:
        json.loads(cards_json_bytes)
    except json.JSONDecodeError as exc:
        st.error(f"Invalid JSON: {exc}")
        return

    card_size: Literal["A6", "A5"] = st.radio(  # type: ignore[assignment]
        "Card size",
        ["A6", "A5"],
        horizontal=True,
        key=f"{key_prefix}_card_size",
        help="A6 → 4 cards per A4 sheet · A5 → 2 cards per A4 sheet",
    )

    selected_model = st.text_input(
        "Image model (Runware)",
        value=RUNWARE_MODEL,
        key=f"{key_prefix}_runware_model",
        help="Runware model ID, e.g. runware:400@2 (FLUX Schnell), runware:101@1 (SDXL), runware:5@4 (FLUX Dev)",
    )

    force_regen = st.checkbox(
        "Force re-generate images (ignore cache)",
        value=False,
        key=f"{key_prefix}_force_regen",
        help="Always call the Runware API even if a cached image exists for this prompt.",
    )

    if st.button("Render deck", type="primary", key=f"{key_prefix}_render_btn"):
        _do_render(
            cards_json_bytes=cards_json_bytes,
            card_size=card_size,
            key_prefix=key_prefix,
            runware_model=selected_model,
            force_regen_images=force_regen,
        )


def _do_render(
    *,
    cards_json_bytes: bytes,
    card_size: Literal["A6", "A5"],
    key_prefix: str,
    runware_model: str | None = None,
    force_regen_images: bool = False,
) -> None:
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        cards_json_path = tmp_dir / "cards.json"
        cards_json_path.write_bytes(cards_json_bytes)

        renders_dir = tmp_dir / "renders"
        merged_path = tmp_dir / "deck.pdf"

        with st.status("Rendering…", expanded=True) as status:
            st.write("Rendering cards…")
            pdf_paths = cards_json_to_pdfs(
                cards_json_path,
                renders_dir,
                IMAGE_CACHE_DIR,
                runware_model=runware_model,
                force_regen_images=force_regen_images,
            )
            st.write(f"{len(pdf_paths)} cards rendered.")
            st.write("Merging into print sheet…")
            merge_pdfs_to_print(pdf_paths, merged_path, card_size=card_size)
            status.update(label="Done.", state="complete", expanded=False)

        merged_pdf_bytes = merged_path.read_bytes()
        card_png_pairs = _card_pdfs_to_pngs(pdf_paths, tmp_dir / "card_pngs")

    st.divider()
    _download_row_and_viewer(
        merged_pdf_bytes,
        "deck.pdf",
        [("⬇ PNGs (ZIP)", _build_zip(card_png_pairs), "deck_cards.zip", "application/zip")],
        key_prefix,
    )


def _card_pdfs_to_pngs(
    pdf_paths: list[Path],
    output_dir: Path,
    dpi: int = 150,
) -> list[tuple[str, bytes]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pairs: list[tuple[str, bytes]] = []
    for i, pdf_path in enumerate(sorted(pdf_paths, key=lambda p: p.stem)):
        png_dir = output_dir / f"{i:04d}"
        pngs = pdf_to_pngs(pdf_path, png_dir, dpi=dpi)
        if pngs:
            pairs.append((f"card_{i + 1:04d}.png", pngs[0].read_bytes()))
    return pairs


def _build_zip(pairs: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in pairs:
            zf.writestr(f"cards/{name}", data)
    return buf.getvalue()
