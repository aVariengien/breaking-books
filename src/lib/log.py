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

    # For agent SDK messages:
    log.log_message(message)
"""

import json
import logging
from datetime import datetime
from typing import Any

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
# Agent SDK message dispatcher
# ---------------------------------------------------------------------------


def log_message(message: Any) -> None:
    """Log one agent SDK message at the appropriate level."""
    if isinstance(message, UserMessage):
        content = message.content if isinstance(message.content, str) else repr(message.content)
        _agent_logger.debug("User: %s", content)

    elif isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock) and block.text.strip():
                _agent_logger.info(block.text.rstrip())
            elif isinstance(block, ThinkingBlock):
                _agent_logger.debug("Thinking: %s", block.thinking)
            elif isinstance(block, ToolUseBlock):
                _agent_logger.info(
                    "Tool %s\n%s",
                    block.name,
                    json.dumps(block.input, indent=2, ensure_ascii=False),
                )
            elif isinstance(block, ToolResultBlock):
                content = _coerce_content(block.content)
                if block.is_error:
                    _agent_logger.error("Tool result (error): %s", content)
                else:
                    _agent_logger.info("Tool result: %s", content)

    elif isinstance(message, SystemMessage):
        _agent_logger.debug("System: %s", message.subtype)

    elif isinstance(message, ResultMessage):
        cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd else "N/A"
        if message.is_error:
            _agent_logger.error(
                "Agent finished with error — turns=%d cost=%s", message.num_turns, cost
            )
        else:
            _agent_logger.info(
                "Agent done — turns=%d cost=%s session=%s",
                message.num_turns,
                cost,
                message.session_id,
            )

    else:
        _agent_logger.debug(repr(message))


def _coerce_content(content: Any) -> str:
    if isinstance(content, list):
        return "\n".join(
            c.get("text", repr(c)) if isinstance(c, dict) else repr(c) for c in content
        )
    return str(content or "")
