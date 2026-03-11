"""Logging configuration for the Breaking Books project.

Call ``setup()`` once at startup; all ``bb.*`` loggers then inherit the
Rich console handler and file handler automatically.

Usage:
    from lib import log
    log.setup()   # once, before any pipeline step

    # In any module:
    import logging
    logger = logging.getLogger("bb.tools.render")
    logger.info("Rendering %d cards…", n)

    # For ADK events:
    log.log_message(event)
"""

import json
import logging
from datetime import datetime
from typing import Any

from rich.logging import RichHandler

from lib.constants import LOG_PATH

_agent_logger = logging.getLogger("bb.agent")


def setup() -> None:
    """Configure the bb root logger: Rich console handler + plain file handler.

    All bb.* child loggers (bb.main, bb.agent, bb.tools, …) inherit these
    handlers automatically, so this only needs to be called once at startup.
    """
    root = logging.getLogger("bb")
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    console_handler = RichHandler(show_path=False, rich_tracebacks=True)
    console_handler.setLevel(logging.DEBUG)
    root.addHandler(console_handler)

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8", mode="a")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s", datefmt="%H:%M:%S")
    )
    root.addHandler(file_handler)

    root.info("=== session started: %s ===", datetime.now().isoformat(timespec="seconds"))


# ---------------------------------------------------------------------------
# ADK Event dispatcher
# ---------------------------------------------------------------------------


def log_message(event: Any) -> None:
    """Log one ADK Event at the appropriate level."""
    try:
        _log_event(event)
    except Exception as exc:  # noqa: BLE001
        _agent_logger.debug("Could not log event %r: %s", type(event).__name__, exc)


def _log_event(event: Any) -> None:
    author = getattr(event, "author", None) or "?"
    content = getattr(event, "content", None)
    partial = getattr(event, "partial", False)

    # User message
    if author == "user":
        if content and content.parts:
            for part in content.parts:
                text = getattr(part, "text", None)
                if text and text.strip():
                    _agent_logger.debug("User: %s", text.rstrip())
        return

    # Function call requests (agent asking to use a tool)
    fn_calls = _get_function_calls(event)
    for fc in fn_calls:
        name = getattr(fc, "name", "?")
        args = getattr(fc, "args", {})
        _agent_logger.info(
            "Tool %s\n%s",
            name,
            json.dumps(args, indent=2, ensure_ascii=False, default=str),
        )

    # Function responses (tool results)
    fn_responses = _get_function_responses(event)
    for fr in fn_responses:
        name = getattr(fr, "name", "?")
        response = getattr(fr, "response", {})
        text = _extract_response_text(response)
        _agent_logger.info("Tool result [%s]: %s", name, text[:500] if text else repr(response))

    # Text content — always scan all parts so thoughts before tool calls are logged.
    if content and content.parts:
        for part in content.parts:
            text = getattr(part, "text", None)
            is_thought = bool(getattr(part, "thought", False))
            if text and text.strip():
                if is_thought:
                    if not partial:
                        _agent_logger.debug("💭 Thinking: %s", text.rstrip())
                elif partial:
                    _agent_logger.debug("(streaming) %s", text.rstrip())
                else:
                    _agent_logger.info(text.rstrip())

    # Final response marker
    is_final = False
    try:
        is_final = event.is_final_response()
    except Exception:
        pass
    if is_final and not fn_calls and not fn_responses:
        _agent_logger.debug("Agent produced final response")


def _get_function_calls(event: Any) -> list:
    try:
        result = event.get_function_calls()
        return result if result else []
    except Exception:
        return []


def _get_function_responses(event: Any) -> list:
    try:
        result = event.get_function_responses()
        return result if result else []
    except Exception:
        return []


def _extract_response_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        # ADK wraps function return value in {"result": ...}
        val = response.get("result", response)
        if isinstance(val, str):
            return val
        return json.dumps(val, ensure_ascii=False, default=str)
    return str(response)
