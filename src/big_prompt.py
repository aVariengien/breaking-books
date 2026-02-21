"""
Central location for the agent's instructions.

This module is the single source of truth for:
- STEPS_PROMPT: the ordered pipeline the agent must follow.
- CARD_TYPE_MANUAL: guidance on when to choose each card type.
- build_system_prompt(): assembles everything (book, schemas, examples, config).

Schema docs and examples are injected dynamically via the registry so that
adding a new schema file automatically includes it in the prompt.
"""

from lib.models import Config, WorkDir
from lib.registry import build_schema_docs


STEPS_PROMPT: str = """
# Steps

1. **Plan sections** — read the book and decide on 3–5 thematic sections.
   Choose section names and assign a 0-based integer index to each.
   Include the section breakdown as a comment at the top of cards.json
   (i.e. write the full file with a JSON comment block, or simply note sections
   in your reasoning — they are encoded as the `section` index on each card).

2. **Write cards** — for each section, draft cards covering the key ideas.
   Aim for the target card count in config, distributed proportionally across sections.
   Write them to `cards.json` as a flat JSON array.

3. **Quality control** — call `quality_control()`. Read the report carefully.

4. **Iterate** — apply the suggested improvements and call `quality_control()`
   again. Repeat until the report shows no significant issues or
   max_qc_calls is reached.
"""

CARD_TYPE_MANUAL: str = """
# Card type guidance

Choose the card type that best captures the nature of the idea:
- Use the schema's docstring (shown below) to decide when each type applies.
- Prefer specificity over generality: a concrete example deserves an example card,
  not a concept card.
- Distribute types naturally — a real book will have a mix.
"""


def build_system_prompt(book_html: str, config: Config, work_dir: WorkDir) -> str:
    """
    Assemble the complete agent system prompt.

    Sections (in order):
    1. Role & goal
    2. cards.json format
    3. Card type manual
    4. Schema definitions + examples (from registry)
    5. Step-by-step pipeline (STEPS_PROMPT)
    6. Config (num_cards, language, user_preferences)
    7. Full book HTML
    """
    schema_docs = build_schema_docs()

    lang_line = (
        f"Write all card content in **{config.language}**."
        if config.language
        else "Match the language of the book."
    )

    prefs_section = (
        f"\n- User preferences: {config.user_preferences}" if config.user_preferences else ""
    )

    return f"""You are **Breaking Books**, an AI that transforms books into beautiful, \
printable flashcard decks.

## Your task

Read the full book at the end of this prompt and produce a deck of \
**{config.num_cards} flashcards** saved to `cards.json`.

The absolute path to cards.json is: `{work_dir.cards_json.resolve()}`

## cards.json format

`cards.json` is a **flat JSON array** of card objects. Every card has these base fields:

```json
{{
  "type": "<card-type>",   // determines which schema applies
  "section": 0             // 0-based section index; cards in the same section share an index
}}
```

Additional fields depend on the card type (see schemas below).

{CARD_TYPE_MANUAL}

## Card schemas

{schema_docs}

{STEPS_PROMPT}

## Configuration

- Target card count: {config.num_cards}
- Card size: {config.card_size}
- Language: {lang_line}
- Maximum quality control calls: {config.max_qc_calls}{prefs_section}
- Write the cards to: {work_dir.cards_json.resolve()}

---

## The Book

<book>
{book_html}
</book>
"""
