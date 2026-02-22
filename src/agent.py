"""Breaking Books agent — orchestrated by the Claude Agent SDK."""

import asyncio
from typing import Any, AsyncGenerator

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    create_sdk_mcp_server,
    tool,
)
from claude_agent_sdk import McpSdkServerConfig

from big_prompt import build_initial_query, build_system_prompt
from lib.models import Config, OutDir, WorkDir


async def run_agent(
    book_html: str,
    config: Config,
    work_dir: WorkDir,
    out_dir: OutDir,
    *,
    resume: bool = False,
    instructions: str = "",
) -> AsyncGenerator[Any, None]:
    """Async generator that yields all SDK messages from the agent loop."""
    session_id: str | None = None
    if resume and out_dir.session_id_path.exists():
        session_id = out_dir.session_id_path.read_text().strip() or None

    if resume and instructions:
        prompt = instructions
    elif resume:
        prompt = "Continue improving the flashcard deck based on the last QC report."
    else:
        prompt = build_initial_query(book_html)

    options = ClaudeAgentOptions(
        system_prompt=build_system_prompt(config, work_dir),
        mcp_servers={"bb": _make_agent_tools(work_dir, config, out_dir)},
        allowed_tools=["Read", "Write", "Edit", "Glob", "mcp__bb__quality_control"],
        permission_mode="acceptEdits",
        cwd=str(work_dir.root),
        resume=session_id,
        model="haiku",
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_messages():
            yield message
            if isinstance(message, ResultMessage):
                out_dir.session_id_path.write_text(message.session_id)
                break


def _make_agent_tools(work_dir: WorkDir, config: Config, out_dir: OutDir) -> "McpSdkServerConfig":
    call_count = [0]

    @tool(
        "quality_control",
        (
            "Run quality control on the current cards.json deck. "
            "Returns a natural-language report of suggested improvements and saves a snapshot. "
            f"Call at most {config.max_qc_calls} times."
        ),
        {},
    )
    async def qc_tool(args: dict[str, Any]) -> dict[str, Any]:
        if call_count[0] >= config.max_qc_calls:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Quality control limit reached ({config.max_qc_calls} calls). "
                            "No further QC runs are allowed. Submit the deck as-is."
                        ),
                    }
                ]
            }
        call_count[0] += 1
        from tools.quality_control import quality_control

        report = await asyncio.to_thread(
            quality_control, work_dir.cards_json, config, work_dir, out_dir
        )
        return {"content": [{"type": "text", "text": report}]}

    return create_sdk_mcp_server(name="breaking-books", tools=[qc_tool])
