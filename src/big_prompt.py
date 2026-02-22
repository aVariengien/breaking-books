"""Central location for the agent's instructions."""

import json

from lib.models import Config, WorkDir
from lib.registry import get_all_schema_classes


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------
# Placeholders (filled by build_system_prompt):
#   {num_cards}       — target card count
#   {cards_json_path} — absolute path to cards.json
#   {schema_docs}     — rendered schema reference (from build_schema_docs)
#   {max_qc_calls}    — max quality-control iterations
#   {card_size}       — physical card size
#   {lang_line}       — language instruction
#   {prefs_section}   — optional user preferences line
#   {book_html}       — full book HTML
#
# Note: literal {{ / }} in JSON snippets survive str.format() as { / }.
# Dynamic content (schema_docs, book_html) is brace-escaped before formatting.
# ---------------------------------------------------------------------------

PROMPT = """\
You are **Breaking Books**, an AI that transforms books into beautiful, printable flashcard decks.

## Your task

Read the full book at the end of this prompt and produce a deck of \
**{num_cards} flashcards** saved to `cards.json`.

The absolute path to cards.json is: `{cards_json_path}`

## cards.json format

`cards.json` is a **BBGame object** with the following structure:

```json
{{
  "book_plan": "Strategic overview of sections and key ideas to cover",
  "visual_identity": {{
    "description": "Freeform description of the visual style and aesthetic",
    "title_font": "Font name for card titles (e.g., 'Arial')",
    "body_font": "Font name for card body text (e.g., 'Georgia')",
    "section_themes": [
      {{"main_color": "#FFFFFF", "dark_color": "#2C3E50", "accent_color": "#FF6B6B"}},
      {{"main_color": "#F8F9FA", "dark_color": "#34495E", "accent_color": "#4ECDC4"}},
      {{"main_color": "#ECF0F1", "dark_color": "#1A1A1A", "accent_color": "#45B7D1"}}
    ]
  }},
  "cards": [
    {{
      "type": "<card-type>",   // determines which schema applies
      "section": 0             // 0-based section index; cards in the same section share an index
    }},
    // ... more cards
  ]
}}
```

Additional fields in each card depend on the card type (see schemas below).

## Card type guidance

Choose the card type that best captures the nature of the idea:
- Use the schema's description (shown below) to decide when each type applies.
- Prefer specificity over generality: a concrete example deserves an example card,
  not a concept card.
- Distribute types naturally — a real book will have a mix.

## Card schemas

{schema_docs}

## Steps

1. **Plan sections** — read the book and decide on 3–5 thematic sections.
   Choose section names and assign a 0-based integer index to each.
   Write a `book_plan` summarizing the section breakdown and strategic approach.

2. **Define visual identity** — create a `visual_identity` object with:
   - `description`: freeform aesthetic direction (mood, color scheme, visual metaphors, etc.)
   - `title_font`: choose a font name for card titles
   - `body_font`: choose a font name for card body text
   - `section_themes`: array of themes, one per section. Each theme has:
     - `main_color`: primary background color (hex code)
     - `dark_color`: dark text/foreground color (hex code)
     - `accent_color`: highlight/accent color (hex code)

3. **Write cards** — for each section, draft cards covering the key ideas.
   Aim for the target card count in config, distributed proportionally across sections.
   Write them as the `cards` array inside the BBGame object.

4. **Quality control** — call `quality_control()`. Read the report carefully.

5. **Iterate** — apply the suggested improvements and call `quality_control()`
   again. Repeat until the report shows no significant issues or
   `max_qc_calls` is reached.

## Configuration

- Target card count: {num_cards}
- Card size: {card_size}
- Language: {lang_line}
- Maximum quality-control calls: {max_qc_calls}{prefs_section}
- Write the cards to: `{cards_json_path}`

---

## The Book

<book>
{book_html}
</book>
"""


# ---------------------------------------------------------------------------
# Schema reference builder
# ---------------------------------------------------------------------------


def _clean_json_schema(schema: dict) -> dict:
    """Strip noisy Pydantic metadata from a JSON schema for use in the prompt.

    Removes top-level title/description (rendered separately) and per-property
    title keys (field names are self-evident).
    """
    result: dict = {}
    for key in ("type", "properties", "required"):
        if key not in schema:
            continue
        if key == "properties":
            result["properties"] = {
                name: {k: v for k, v in prop.items() if k != "title"}
                for name, prop in schema["properties"].items()
            }
        else:
            result[key] = schema[key]
    return result


def build_schema_docs() -> str:
    """Render a human-readable reference for all card schemas, for the agent prompt."""
    sections: list[str] = []

    for cls in get_all_schema_classes():
        type_val = cls.model_fields["type"].default
        lines: list[str] = []

        # --- heading ---
        lines.append(f'### `{cls.__name__}` — `"type": "{type_val}"`')

        # --- description: class docstring ---
        if cls.__doc__:
            lines.append("")
            lines.append(cls.__doc__.strip())

        # --- JSON Schema ---
        schema = _clean_json_schema(cls.model_json_schema())
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(schema, ensure_ascii=False, indent=2))
        lines.append("```")

        # --- examples ---
        examples = cls.get_examples()
        if examples:
            lines.append("")
            label = "Example" if len(examples) == 1 else "Examples"
            lines.append(f"**{label}:**")
            lines.append("```json")
            for ex in examples:
                lines.append(json.dumps(ex.model_dump(), ensure_ascii=False, indent=2))
            lines.append("```")

        sections.append("\n".join(lines))

    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_system_prompt(book_html: str, config: Config, work_dir: WorkDir) -> str:
    """Assemble the complete agent system prompt."""
    schema_docs = build_schema_docs()

    lang_line = (
        f"Write all card content in **{config.language}**."
        if config.language
        else "Match the language of the book."
    )
    prefs_section = (
        f"\n- User preferences: {config.user_preferences}" if config.user_preferences else ""
    )

    # Escape braces in dynamic content so str.format() doesn't choke on them.
    def _esc(s: str) -> str:
        return s.replace("{", "{{").replace("}", "}}")

    return PROMPT.format(
        num_cards=config.num_cards,
        cards_json_path=work_dir.cards_json.resolve(),
        card_size=config.card_size,
        lang_line=lang_line,
        max_qc_calls=config.max_qc_calls,
        prefs_section=prefs_section,
        schema_docs=_esc(schema_docs),
        book_html=_esc(book_html),
    )
