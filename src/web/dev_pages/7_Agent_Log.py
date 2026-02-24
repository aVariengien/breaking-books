"""Dev page: upload and display a saved agent log JSON."""

import json
import time

import streamlit as st

from web.utils import build_tool_names, render_agent_log, render_message, update_status_for_message

st.title("Agent Log Viewer")
st.markdown("Upload an `agent_log.json` file (downloaded from the Generator page) to inspect it.")

uploaded = st.file_uploader("Agent log JSON", type=["json"], label_visibility="collapsed")
if uploaded is None:
    st.stop()
assert uploaded is not None

try:
    messages: list[dict] = json.loads(uploaded.read())
except json.JSONDecodeError as e:
    st.error(f"Invalid JSON: {e}")
    st.stop()

if not isinstance(messages, list):
    st.error("Expected a JSON array of messages.")
    st.stop()

result = next((m for m in reversed(messages) if m.get("__type__") == "ResultMessage"), None)
summary_parts = []
if result:
    if result.get("total_cost_usd"):
        summary_parts.append(f"${result['total_cost_usd']:.4f}")
    if result.get("num_turns"):
        summary_parts.append(f"{result['num_turns']} turns")
    if result.get("duration_ms"):
        summary_parts.append(f"{result['duration_ms'] / 1000:.0f}s")
summary = " · ".join(summary_parts)

col1, col2 = st.columns([1, 1])
view_mode = col1.radio("Mode", ["Static", "Replay"], horizontal=True, label_visibility="collapsed")
delay = col2.slider("Delay (s)", 0.0, 3.0, 1.0, 0.1, disabled=(view_mode == "Static"))

if view_mode == "Static":
    with st.status(f"Agent log — {summary}", state="complete", expanded=True):
        render_agent_log(messages)
else:
    if st.button("▶ Replay", type="primary"):
        is_error = result and result.get("is_error")
        tool_names = build_tool_names(messages)

        with st.status("Starting…", expanded=True) as status:
            for msg in messages:
                update_status_for_message(status, msg)
                render_message(msg, tool_names)
                time.sleep(delay)

            status.update(
                label=f"Generation failed — {summary}" if is_error else f"Agent log — {summary}",
                state="error" if is_error else "complete",
                expanded=False,
            )
