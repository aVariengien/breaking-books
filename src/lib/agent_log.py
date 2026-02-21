"""Logging configuration for the Breaking Books agent.

Usage:
    from lib import agent_log
    agent_log.setup(out_dir.agent_log_path)   # once, before the loop
    agent_log.log_message(message)             # for each SDK message
"""

import json
import logging
from datetime import datetime
from pathlib import Path
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

logger = logging.getLogger("bb.agent")


def setup(log_path: Path) -> None:
    """Configure the bb.agent logger: Rich console handler + plain file handler."""
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers.clear()

    console_handler = RichHandler(show_path=False, rich_tracebacks=True)
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8", mode="a")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
    )
    logger.addHandler(file_handler)

    logger.info("=== session started: %s ===", datetime.now().isoformat(timespec="seconds"))


def log_message(message: Any) -> None:
    """Log one SDK agent message at the appropriate level."""
    if isinstance(message, UserMessage):
        content = message.content if isinstance(message.content, str) else repr(message.content)
        logger.debug("User: %s", content)

    elif isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock) and block.text.strip():
                logger.info(block.text.rstrip())
            elif isinstance(block, ThinkingBlock):
                logger.debug("Thinking: %s", block.thinking[:300])
            elif isinstance(block, ToolUseBlock):
                logger.info(
                    "Tool %s\n%s",
                    block.name,
                    json.dumps(block.input, indent=2, ensure_ascii=False),
                )
            elif isinstance(block, ToolResultBlock):
                content = _coerce_content(block.content)
                if block.is_error:
                    logger.error("Tool result (error): %s", content)
                else:
                    logger.info("Tool result: %s", content)

    elif isinstance(message, SystemMessage):
        logger.debug("System: %s", message.subtype)

    elif isinstance(message, ResultMessage):
        cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd else "N/A"
        if message.is_error:
            logger.error("Agent finished with error — turns=%d cost=%s", message.num_turns, cost)
        else:
            logger.info(
                "Agent done — turns=%d cost=%s session=%s",
                message.num_turns,
                cost,
                message.session_id,
            )

    else:
        logger.debug(repr(message))


def _coerce_content(content: Any) -> str:
    if isinstance(content, list):
        return "\n".join(
            c.get("text", repr(c)) if isinstance(c, dict) else repr(c) for c in content
        )
    return str(content or "")
