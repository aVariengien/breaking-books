"""Streamlit UI for Breaking Books v2."""

from lib.models import Config, OutDir, WorkDir


# ------------------------------------------------------------------
# Phase routing
# ------------------------------------------------------------------


def main() -> None:
    """Entry point. Routes between configure → generate → review phases."""
    raise NotImplementedError()


# ------------------------------------------------------------------
# Phases
# ------------------------------------------------------------------


def configure_phase() -> None:
    """
    Step 1: File upload (EPUB), card count, language, user preferences.
    On submit, builds Config and transitions to generation_phase.
    """
    raise NotImplementedError()


def generation_phase(config: Config, work_dir: WorkDir, out_dir: OutDir) -> None:
    """
    Step 2: Stream agent progress in real time.
    Shows a live preview of cards.json as the agent writes it.
    Allows the user to pause/inspect between QC iterations.
    """
    raise NotImplementedError()


def review_phase(config: Config, work_dir: WorkDir, out_dir: OutDir) -> None:
    """
    Step 3: Display the finished deck.
    - Card gallery with rendered PNGs.
    - Latest QC report.
    - Follow-up text box → resumes the agent with new instructions.
    - Download buttons for cards.json and printable PDF.
    """
    raise NotImplementedError()


if __name__ == "__main__":
    main()
