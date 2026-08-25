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
from lib.utils import deck_filename_from_json
from tools.merge_pdfs import merge_pdfs_to_print
from tools.pdf_to_pngs import pdf_to_pngs
from tools.render_template import cards_json_to_pdfs


# ---------------------------------------------------------------------------
# Token pricing
# ---------------------------------------------------------------------------

# Prices in USD per 1M tokens (cached_input, non_cached_input, output).
# Thinking tokens are billed at the output rate.
# Pro prices use the <=200k-token tier; >200k tier is $4.00/$18.00/$0.40 respectively.
# Sources: Google AI Studio + Anthropic pricing pages, Aug 2026.
_MODEL_PRICING: dict[str, tuple[float, float, float]] = {
    #                                  cached   non-cached  output
    # Gemini 3.7 Flash — introductory rates, in effect through 2026-12-31.
    # From 2027-01-01 these double to (0.15, 1.50, 7.50).
    "gemini-3.7-flash":                (0.075,   0.75,      3.75),
    "gemini-3.1-flash-lite-preview":   (0.025,   0.25,      1.50),
    "gemini-3.1-pro-preview":          (0.20,    2.00,     12.00),
    "gemini-3.1-pro-preview-customtools": (0.20, 2.00,     12.00),
    "gemini-2.5-flash-preview":        (0.0375,  0.15,      0.60),
    "gemini-2.5-pro-preview":          (0.3125,  1.25,     10.00),
    "gemini-2.0-flash":                (0.025,   0.10,      0.40),
    "gemini-2.0-flash-lite":           (0.01875, 0.075,     0.30),
    # Anthropic — cache hits price used as cached_input rate
    "claude-sonnet-5":                 (0.30,    3.00,     15.00),
    "claude-sonnet-4-6":               (0.30,    3.00,     15.00),
}


def _estimate_cost(
    model: str,
    non_cached_prompt_tokens: int,
    cached_prompt_tokens: int,
    output_tokens: int,
) -> float | None:
    """Return estimated cost in USD, or None if the model is not in the pricing table."""
    # Strip provider prefix (e.g. "gemini/gemini-3.7-flash" → "gemini-3.7-flash")
    key = model.split("/")[-1]
    pricing = _MODEL_PRICING.get(key)
    if pricing is None:
        return None
    cached_rate, non_cached_rate, output_rate = pricing
    cost = (cached_prompt_tokens / 1_000_000) * cached_rate
    cost += (non_cached_prompt_tokens / 1_000_000) * non_cached_rate
    cost += (output_tokens / 1_000_000) * output_rate
    return cost


# ---------------------------------------------------------------------------
# ADK Event rendering
# ---------------------------------------------------------------------------


def tool_label_plain(name: str, args: dict) -> str:
    """Label without emoji, suitable for the st.status() header."""
    if name == "write_file":
        return f"Write {Path(args.get('file_path', '?')).name}"
    if name == "edit_file":
        return f"Edit {Path(args.get('file_path', '?')).name}"
    if name == "read_file":
        return f"Read {Path(args.get('path', '?')).name}"
    if name == "grep_files":
        return f"Grep {args.get('pattern', '?')}"
    if name == "quality_control":
        return "Quality Control"
    return name


def _tool_label(name: str, args: dict) -> str:
    if name == "write_file":
        return f"✏️ Write → {Path(args.get('file_path', '?')).name}"
    if name == "edit_file":
        return f"✏️ Edit → {Path(args.get('file_path', '?')).name}"
    if name == "read_file":
        return f"📖 Read → {Path(args.get('path', '?')).name}"
    if name == "grep_files":
        return f"🔍 Grep → {args.get('pattern', '?')}"
    if name == "quality_control":
        return "✅ Quality Control"
    return f"🔧 {name}"


def update_status_for_message(status: Any, event: dict, *, elapsed: float | None = None) -> None:
    """Update a st.status() label to reflect the current serialized ADK event.

    Pass ``elapsed`` (seconds since the last update) to include timing in labels,
    e.g. "Thought 3s → Write cards.json". Without it, plain labels are used.
    """
    etype = event.get("__type__")
    if etype == "tool_call":
        name = event.get("name", "")
        args = event.get("args", {})
        plain = tool_label_plain(name, args)
        label = f"Thought {elapsed:.0f}s → {plain}" if elapsed is not None else f"→ {plain}"
        status.update(label=label)
    elif etype == "tool_result":
        label = f"Tool returned ({elapsed:.0f}s)" if elapsed is not None else "Tool returned"
        status.update(label=label)
    elif etype == "text":
        status.update(label="Writing…")
    elif etype == "start":
        status.update(label="Starting…")


def _render_tool_result_content(content: str, tool_name: str | None) -> None:
    """Render tool result content using the appropriate display format for the tool."""
    if tool_name == "quality_control":
        with st.expander("📝 Quality Control output", expanded=True):
            st.markdown(content)
    elif tool_name in ("edit_file", "write_file"):
        pass
    else:
        with st.expander(f"📖 {tool_name} output", expanded=False):
            st.code(content, language=None)


def _render_edit_diff(args: dict) -> None:
    """Render an edit_file call as a unified diff."""
    old = args.get("old_string", "")
    new = args.get("new_string", "")
    name = Path(args.get("file_path", "?")).name
    diff_lines = list(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{name}",
            tofile=f"b/{name}",
            n=3,
        )
    )[3:]
    if diff_lines:
        diff_lines = [line.rstrip() for line in diff_lines]
        st.code("\n".join(diff_lines), language="diff")
    else:
        st.caption("(no changes)")


def render_message(event: dict, _tool_names: dict[str, str] | None = None) -> None:
    """Render a single serialized ADK event."""
    etype = event.get("__type__")
    if etype == "thought":
        text = event.get("text", "").strip()
        if text:
            with st.expander("💭 Thinking…", expanded=False):
                st.markdown(text)
    elif etype == "text":
        text = event.get("text", "").strip()
        if text:
            st.markdown(text)
    elif etype == "tool_call":
        name = event.get("name", "tool")
        args = event.get("args", {})
        expanded = name == "edit_file"
        with st.expander(_tool_label(name, args), expanded=expanded):
            if name == "edit_file":
                _render_edit_diff(args)
            else:
                st.code(json.dumps(args, indent=2, ensure_ascii=False), language="json")
    elif etype == "tool_result":
        name = event.get("name", "")
        content = event.get("content", "")
        is_error = event.get("is_error", False)
        if is_error:
            st.error(content)
        elif content.strip():
            _render_tool_result_content(content, name)
    elif etype == "done":
        turns = event.get("turns", 0)
        elapsed_s = event.get("elapsed_s")
        non_cached_prompt_tokens = event.get("non_cached_prompt_tokens", 0)
        cached_prompt_tokens = event.get("cached_prompt_tokens", 0)
        output_tokens = event.get("output_tokens", 0)
        thought_tokens = event.get("thought_tokens", 0)
        model = event.get("model", "")
        total_tokens = non_cached_prompt_tokens + cached_prompt_tokens + output_tokens

        label = f"Done — {turns} turn{'s' if turns != 1 else ''}"
        if elapsed_s is not None:
            mins, secs = divmod(int(elapsed_s), 60)
            time_str = f"{mins}m {secs}s" if mins else f"{secs}s"
            label += f" · {time_str}"
        st.success(label)

        if total_tokens > 0:
            cost = _estimate_cost(model, non_cached_prompt_tokens, cached_prompt_tokens, output_tokens)
            cols = st.columns(5)
            cols[0].metric("Input tokens", f"{non_cached_prompt_tokens:,}")
            cols[1].metric("Cached tokens", f"{cached_prompt_tokens:,}")
            cols[2].metric("Output tokens", f"{output_tokens:,}")
            cols[3].metric("Thinking tokens", f"{thought_tokens:,}")
            if cost is not None:
                cols[4].metric("Est. cost", f"${cost:.4f}")
            else:
                cols[4].metric("Total tokens", f"{total_tokens:,}")
    elif etype == "user":
        text = event.get("text", "")
        if text.strip():
            st.chat_message("user").markdown(text)


def build_tool_names(events: list[dict]) -> dict[str, str]:
    """Build a call_id → tool name mapping from serialized events (kept for compatibility)."""
    return {e["call_id"]: e["name"] for e in events if e.get("__type__") == "tool_call" and e.get("call_id")}


def render_agent_log(events: list[dict]) -> None:
    """Render a list of serialized ADK events."""
    for event in events:
        render_message(event)


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
    if card_pdfs:
        if zip_key not in st.session_state:
            with st.spinner("Converting cards to images…"):
                st.session_state[zip_key] = make_card_images_zip(card_pdfs)
        secondary.append(
            (
                "⬇ Card images",
                st.session_state[zip_key],
                "card-images.zip",
                "application/zip",
            )
        )

    # On-disk snapshots keep their deck-vNNN.pdf names (the version selector parses
    # them); the file the user actually downloads is named after the book.
    download_name = deck_filename_from_json(cards_json_path)
    _download_row_and_viewer(selected_path.read_bytes(), download_name, secondary, key_prefix)


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
        deck_filename_from_json(cards_json_bytes),
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
