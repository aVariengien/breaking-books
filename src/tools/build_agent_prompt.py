"""Construct the system prompt fed to the Breaking Books agent."""

from lib.models import Config


def build_agent_prompt(book_html: str, config: Config) -> str:
    """
    Assemble the full system prompt for the agent.

    Embeds:
    - The complete book HTML (always in context).
    - All schema definitions + examples (from big_prompt.py and registry).
    - User config (num_cards, language, preferences, …).
    - Step-by-step instructions from big_prompt.STEPS_PROMPT.
    """
    raise NotImplementedError()
