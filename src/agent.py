"""
Breaking Books agent — orchestrated by the Anthropic SDK.

The agent runs in an autonomous loop with access to ReadFile, EditFile, and
QualityControl. It terminates when it judges the deck complete (or when
max_qc_calls is exhausted). It can be resumed with follow-up instructions.
"""

import anthropic

from lib.models import Config, OutDir, WorkDir


def run_agent(
    book_html: str,
    config: Config,
    work_dir: WorkDir,
    out_dir: OutDir,
    *,
    resume: bool = False,
    instructions: str = "",
) -> None:
    """
    Run (or resume) the Breaking Books agent loop.

    The agent receives the full book HTML in its system prompt and iteratively:
    1. Reads/edits cards.json in work_dir.
    2. Calls QualityControl to get improvement feedback.
    3. Incorporates feedback until satisfied or max_qc_calls reached.

    Args:
        book_html:    Full book content (from extract_book_content).
        config:       User configuration.
        work_dir:     Agent working directory (TMP/).
        out_dir:      Output + snapshots directory (OUT/).
        resume:       If True, continue from the last agent state.
        instructions: Optional follow-up instructions for a resumed session.
    """
    raise NotImplementedError()


def _make_agent_tools(
    work_dir: WorkDir,
    config: Config,
    out_dir: OutDir,
) -> list[anthropic.types.ToolParam]:
    """
    Build the Anthropic tool definitions exposed to the agent:
    - read_file(path)            → str
    - edit_file(path, content)   → None
    - quality_control()          → str  (report)
    """
    raise NotImplementedError()
