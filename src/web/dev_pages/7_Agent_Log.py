"""Dev page: upload and display a saved agent log JSON."""

import json
import time

import streamlit as st

from web.utils import render_agent_log, render_message, update_status_for_message

st.title("Agent Log Viewer")
st.markdown("Upload an `agent_log.json` file (downloaded from the Generator page) to inspect it.")

uploaded = st.file_uploader("Agent log JSON", type=["json"], label_visibility="collapsed")
if uploaded is None:
    st.stop()
assert uploaded is not None

try:
    events: list[dict] = json.loads(uploaded.read())
except json.JSONDecodeError as e:
    st.error(f"Invalid JSON: {e}")
    st.stop()

if not isinstance(events, list):
    st.error("Expected a JSON array of events.")
    st.stop()

done = next((e for e in reversed(events) if e.get("__type__") == "done"), None)
summary_parts = []
if done and done.get("turns"):
    turns = done["turns"]
    summary_parts.append(f"{turns} turn{'s' if turns != 1 else ''}")
if done and done.get("elapsed_s") is not None:
    elapsed_s = int(done["elapsed_s"])
    mins, secs = divmod(elapsed_s, 60)
    summary_parts.append(f"{mins}m {secs}s" if mins else f"{secs}s")
tool_calls = sum(1 for e in events if e.get("__type__") == "tool_call")
if tool_calls:
    summary_parts.append(f"{tool_calls} tool calls")
summary = " · ".join(summary_parts) or "no summary"

col1, col2 = st.columns([1, 1])
view_mode = col1.radio("Mode", ["Static", "Replay"], horizontal=True, label_visibility="collapsed")
delay = col2.slider("Delay (s)", 0.0, 3.0, 1.0, 0.1, disabled=(view_mode == "Static"))

if view_mode == "Static":
    with st.status(f"Agent log — {summary}", state="complete", expanded=True):
        render_agent_log(events)
else:
    if st.button("▶ Replay", type="primary"):
        with st.status("Starting…", expanded=True) as status:
            for event in events:
                update_status_for_message(status, event)
                render_message(event)
                time.sleep(delay)

            status.update(
                label=f"Agent log — {summary}",
                state="complete",
                expanded=False,
            )
