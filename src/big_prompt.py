"""
Central location for the agent's instructions.

This module is the single source of truth for:
- STEPS_PROMPT: the ordered pipeline the agent must follow.
- CARD_TYPE_MANUAL: guidance on when to choose each card type.
- build_system_prompt(): assembles everything (book, schemas, examples, config).

Schema docs and examples are injected dynamically via the registry so that
adding a new schema file automatically includes it in the prompt.
"""

from lib.models import Config


STEPS_PROMPT: str = """
# Steps

1. **Plan sections** — read the book and decide on 3–5 thematic sections.
   Write section names + 1-paragraph introductions to cards.json.

2. **Write cards** — for each section, draft cards covering the key ideas.
   Aim for the target card count in config, distributed proportionally.

3. **Quality control** — call quality_control(). Read the report carefully.

4. **Iterate** — apply the suggested improvements and call quality_control()
   again. Repeat until the report shows no significant issues or
   max_qc_calls is reached.
"""

CARD_TYPE_MANUAL: str = """
# When to choose each card type

See the schema definitions below for the full field specs.
Descriptions and usage guidance are embedded in each schema's docstring.
"""


def build_system_prompt(book_html: str, config: Config) -> str:
    """
    Assemble the complete agent system prompt.

    Sections (in order):
    1. Role & goal
    2. Card type manual
    3. Schema definitions + examples (from registry)
    4. Step-by-step pipeline (STEPS_PROMPT)
    5. Config (num_cards, language, user_preferences)
    6. Full book HTML
    """
    raise NotImplementedError()
