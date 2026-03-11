"""Breaking Books agent — orchestrated by Google ADK with LiteLLM."""

import asyncio
import re
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.planners import BuiltInPlanner
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from big_prompt import build_initial_query, build_system_prompt
from lib.models import Config, OutDir, WorkDir

_APP_NAME = "breaking-books"
_USER_ID = "bb-user"


def _resolve_model(model_str: str):
    """Return the appropriate model object for the given LiteLLM-style model string.

    Gemini models (gemini/...) use ADK's native integration for best performance.
    All other models use LiteLlm.
    """
    if model_str.startswith("gemini/"):
        # Native ADK Gemini: strip the "gemini/" prefix
        return model_str[len("gemini/"):]
    return LiteLlm(model=model_str)


async def run_agent(
    book_html: str,
    config: Config,
    work_dir: WorkDir,
    out_dir: OutDir,
    *,
    resume: bool = False,
    instructions: str = "",
) -> AsyncGenerator[Any, None]:
    """Async generator that yields all ADK Events from the agent loop."""
    session_id: str | None = None
    if resume and out_dir.session_id_path.exists():
        session_id = out_dir.session_id_path.read_text().strip() or None

    if session_id is None:
        session_id = str(uuid.uuid4())

    if resume and instructions:
        prompt = instructions
    elif resume:
        prompt = "Continue improving the flashcard deck based on the last QC report."
    else:
        prompt = build_initial_query(book_html)

    session_service = InMemorySessionService()

    existing = await session_service.get_session(
        app_name=_APP_NAME, user_id=_USER_ID, session_id=session_id
    )
    if existing is None:
        await session_service.create_session(
            app_name=_APP_NAME, user_id=_USER_ID, session_id=session_id
        )

    tools = _make_tools(work_dir, config, out_dir)
    # Enable thinking for native Gemini models (Gemini 3+ supports thinking_level).
    # LiteLLM-backed models skip the planner to avoid compatibility issues.
    resolved_model = _resolve_model(config.model)
    planner = None
    if isinstance(resolved_model, str):
        planner = BuiltInPlanner(
            thinking_config=genai_types.ThinkingConfig(
                include_thoughts=True,
                thinking_level=genai_types.ThinkingLevel.MEDIUM,
            )
        )
    agent = LlmAgent(
        name="breaking_books_agent",
        model=resolved_model,
        instruction=build_system_prompt(config, work_dir),
        tools=tools,
        planner=planner,
    )
    runner = Runner(agent=agent, app_name=_APP_NAME, session_service=session_service)

    new_message = genai_types.Content(role="user", parts=[genai_types.Part(text=prompt)])

    async for event in runner.run_async(
        user_id=_USER_ID,
        session_id=session_id,
        new_message=new_message,
    ):
        yield event

    out_dir.session_id_path.write_text(session_id)


# ---------------------------------------------------------------------------
# Function tools
# ---------------------------------------------------------------------------


def _make_tools(work_dir: WorkDir, config: Config, out_dir: OutDir) -> list:
    """Build the list of function tools for the agent, scoped to work_dir."""
    base = work_dir.root

    def _resolve(path: str) -> Path:
        """Resolve path relative to work_dir, or absolute if already absolute."""
        p = Path(path)
        return p if p.is_absolute() else base / p

    def read_file(path: str) -> str:
        """Read the contents of a file. The path can be absolute or relative to the working directory."""
        p = _resolve(path)
        if not p.exists():
            return f"Error: File not found: {path}"
        try:
            return p.read_text(encoding="utf-8")
        except Exception as exc:
            return f"Error reading {path}: {exc}"

    def write_file(file_path: str, contents: str) -> str:
        """Write contents to a file, creating parent directories as needed. Overwrites the file if it already exists."""
        p = _resolve(file_path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(contents, encoding="utf-8")
            return f"Successfully wrote {len(contents)} characters to {file_path}"
        except Exception as exc:
            return f"Error writing {file_path}: {exc}"

    def edit_file(file_path: str, old_string: str, new_string: str) -> str:
        """Replace the first occurrence of old_string with new_string in a file. Returns an error if old_string is not found."""
        p = _resolve(file_path)
        if not p.exists():
            return f"Error: File not found: {file_path}"
        try:
            content = p.read_text(encoding="utf-8")
            if old_string not in content:
                return f"Error: old_string not found in {file_path}"
            new_content = content.replace(old_string, new_string, 1)
            p.write_text(new_content, encoding="utf-8")
            return f"Successfully edited {file_path}"
        except Exception as exc:
            return f"Error editing {file_path}: {exc}"

    def grep_files(pattern: str, path: str = ".") -> str:
        """Search for a regex pattern in files. path is relative to the working directory (default: search all files). Returns matching lines with file:line: content format, limited to 200 matches."""
        search_path = _resolve(path)
        if not search_path.exists():
            return f"Error: Path not found: {path}"

        results: list[str] = []
        try:
            files = sorted(search_path.rglob("*")) if search_path.is_dir() else [search_path]
            for f in files:
                if not f.is_file():
                    continue
                try:
                    text = f.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(text.splitlines(), 1):
                        if re.search(pattern, line):
                            rel = f.relative_to(base) if f.is_relative_to(base) else f
                            results.append(f"{rel}:{i}: {line.rstrip()}")
                            if len(results) >= 200:
                                break
                except Exception:
                    pass
                if len(results) >= 200:
                    break
        except Exception as exc:
            return f"Error: {exc}"

        if not results:
            return "No matches found."
        if len(results) >= 200:
            results.append("... (truncated at 200 matches)")
        return "\n".join(results)

    call_count = [0]

    async def quality_control() -> str:
        """Run quality control on the current cards.json deck. Returns a natural-language report of suggested improvements and saves a versioned snapshot. Call this after writing or updating cards.json."""
        if call_count[0] >= config.max_qc_calls:
            return (
                f"Quality control limit reached ({config.max_qc_calls} calls). "
                "No further QC runs are allowed. Submit the deck as-is."
            )
        call_count[0] += 1
        from tools.quality_control import quality_control as _qc

        return await asyncio.to_thread(_qc, work_dir.cards_json, config, work_dir, out_dir)

    return [read_file, write_file, edit_file, grep_files, quality_control]
