"""
Quality Control tool.

Called by the agent after writing or updating cards.json. Runs a multi-step
inspection and returns a natural-language improvement report. Also saves a
versioned snapshot of cards.json + report to OutDir.
"""

import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from cerebras.cloud.sdk import Cerebras
from cerebras.cloud.sdk.types.chat.chat_completion import ChatCompletionResponse
from pydantic import TypeAdapter, ValidationError

from lib.models import Config, OutDir, WorkDir
from schemas import Card

# ------------------------------------------------------------------
# LLM review configuration
# ------------------------------------------------------------------

CEREBRAS_MODEL = "gpt-oss-120b"

LLM_REVIEW_SYSTEM = """\
You are a meticulous editor reviewing a set of flash cards generated from a non-fiction book.
Each card has a title, verbatim book quotes, and an image description.
Your job is to identify concrete, actionable problems — not vague praise or minor nitpicks.
Be direct and specific: quote the offending card title when flagging an issue.
Respond in the same language as the cards.\
"""

LLM_REVIEW_USER = """\
Review the following flash cards and report issues in FOUR sections:

---
## Verdict
One line only. Choose exactly one: "All good", "Nit", or "Needs improvement".
- "All good": no real problems found.
- "Nit": only minor, non-blocking issues (e.g. one slightly vague image description).
- "Changes requested": real problems that should be fixed (wrong language, undefined key \
terms, multiple bad image descriptions).

## 1. Undefined or under-defined terms
Flag only jargon, coined terms, or concepts that are specific to this book or field —
words a general reader would not know without the book's explanation.
DO NOT flag everyday words, common business vocabulary, or widely understood concepts
(e.g. "trust", "conflict", "leadership", "accountability", "results" are all fine).
A term should be flagged only if it is:
- A neologism, a framework name, or a term the book uses in an unusual/specific way, AND
- NOT explained anywhere in the card's own quotes or in any earlier card in the deck.
For each flag: 'Card «TITLE»: the term "TERM" is specific to this book/field but never defined in the deck.'
If no issues, write "No issues."

## 2. Language consistency
- Identify the dominant language of the deck.
- Flag any card (or individual quote) that is in a different language.
- Flag any card whose language is clearly wrong, garbled, or mixed.
For each flag: "Card «TITLE»: DESCRIPTION OF THE LANGUAGE PROBLEM."
If no issues, write "No issues."

## 3. Image description style
A good image description is: photographic (real scene), no text or diagrams, specific about
subject + lighting + mood, roughly similar length and register across all cards.
Flag any card whose image description:
- Describes an illustration, diagram, chart, or abstract concept rather than a real photo scene.
- Is vague (e.g. "a person thinking") without specific visual detail.
- Deviates strongly in length or style from the rest of the deck.
For each flag: "Card «TITLE»: DESCRIPTION OF THE IMAGE STYLE PROBLEM."
If no issues, write "No issues."
---

CARDS (JSON):
{cards_json}
"""

# Verdict keywords the LLM is instructed to use (lowercase for matching)
_VERDICT_ALL_GOOD = "all good"
_VERDICT_NIT = "nit"
_VERDICT_CHANGES_REQUESTED = "changes requested"


def quality_control(
    cards_json_path: Path,
    config: Config,
    work_dir: WorkDir,
    out_dir: OutDir,
) -> str:
    """
    Run full quality control on cards.json.

    Steps (in order):
    1. _check_json_structure  — parse & validate against schemas
    2. _check_section_balance — warn if sections have unequal card counts
    3. _llm_review            — language, style, completeness, interest
    4. _visual_review         — render to PDF/PNG, vision LLM per card

    Saves a versioned snapshot: OUT/cards-vNNN.json + OUT/qc-report-vNNN.md.

    Returns a natural-language string listing possible improvements,
    which the agent can incorporate (or not) in subsequent edits.
    """
    version = out_dir.next_version()
    sections: list[str] = []
    # Severity accumulated across steps: 0=all good, 1=nit, 2=needs improvement
    severity = 0

    # Step 1 — JSON structure
    structure_errors = _check_json_structure(cards_json_path)
    if structure_errors:
        sections.append(
            "## JSON structure errors\n\n" + "\n".join(f"- {e}" for e in structure_errors)
        )
        report = _prepend_verdict("Changes requested", "\n\n".join(sections))
        if cards_json_path.exists():
            shutil.copy(cards_json_path, out_dir.cards_json_path(version))
        out_dir.qc_report_path(version).write_text(report, encoding="utf-8")
        return report  # no point continuing if schema is broken

    from lib.models import BBGame

    game_data = json.loads(cards_json_path.read_text(encoding="utf-8"))
    game = BBGame.model_validate(game_data)
    cards = [c.model_dump() for c in game.cards]

    # Step 2 — Section balance and visual identity consistency
    balance_text, balance_severity = _check_section_balance(cards, game, config)
    severity = max(severity, balance_severity)
    sections.append(f"## Card count and section balance\n\n{balance_text}")

    # Step 3 — LLM review
    try:
        llm_text, llm_severity = _llm_review(cards, config)
        severity = max(severity, llm_severity)
        sections.append(f"## LLM review\n\n{llm_text}")
    except Exception as exc:  # noqa: BLE001
        sections.append(f"## LLM review\n\n(skipped — error: {exc})")

    overall = ["All good", "Nit", "Changes requested"][severity]
    report = _prepend_verdict(overall, "\n\n".join(sections))

    # Save snapshot
    if cards_json_path.exists():
        shutil.copy(cards_json_path, out_dir.cards_json_path(version))
    out_dir.qc_report_path(version).write_text(report, encoding="utf-8")

    return report


def _prepend_verdict(verdict: str, body: str) -> str:
    return f"## Overall verdict: {verdict}\n\n{body}"


# ------------------------------------------------------------------
# Internal steps
# ------------------------------------------------------------------

_card_adapter: TypeAdapter[Card] = TypeAdapter(Card)


def _check_json_structure(cards_json_path: Path) -> list[str]:
    """Parse cards.json; return a list of structural / schema validation errors."""
    from lib.models import BBGame

    if not cards_json_path.exists():
        return [f"File not found: {cards_json_path}"]

    try:
        raw = json.loads(cards_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON: {exc}"]

    errors: list[str] = []

    # Validate the top-level bbGame structure
    try:
        game = BBGame.model_validate(raw)
    except ValidationError as exc:
        for e in exc.errors(include_url=False):
            loc = ".".join(str(p) for p in e["loc"]) if e["loc"] else "(root)"
            errors.append(f"game.{loc}: {e['msg']}")
        return errors

    # Validate each card in the cards array
    for i, card in enumerate(game.cards):
        try:
            _card_adapter.validate_python(card.model_dump())
        except ValidationError as exc:
            for e in exc.errors(include_url=False):
                loc = ".".join(str(p) for p in e["loc"]) if e["loc"] else "(root)"
                errors.append(f"card[{i}].{loc}: {e['msg']}")

    return errors


def _check_section_balance(cards: list[dict], game: Any, config: Config) -> tuple[str, int]:
    """
    Return (human-readable summary, severity) where severity is
    0 (all good), 1 (nit), or 2 (needs improvement).
    Checks both card distribution across sections and visual_identity.section_themes alignment.
    """

    total = len(cards)
    target = config.num_cards
    lines: list[str] = []
    severity = 0

    if total == 0:
        return "The deck is empty — no cards found.", 2

    # Count vs target
    if total < target * 0.7:
        lines.append(
            f"Only {total} cards present (target: {target}). "
            "The deck is significantly under-populated."
        )
        severity = max(severity, 2)
    elif total > target * 1.3:
        lines.append(
            f"{total} cards present (target: {target}). The deck is significantly over-populated."
        )
        severity = max(severity, 2)
    else:
        lines.append(f"{total} cards present (target: {target}). Count is within range.")

    # Section distribution
    section_counts: Counter = Counter(c["section"] for c in cards)
    num_sections = len(section_counts)
    counts = list(section_counts.values())
    largest = max(counts)
    smallest = min(counts)
    avg = total / num_sections

    # Sort sections numerically if possible, otherwise alphabetically
    try:
        sorted_sections = sorted(section_counts.keys(), key=lambda s: int(s))
    except (ValueError, TypeError):
        sorted_sections = sorted(section_counts.keys(), key=str)

    dist_lines = [f"  Section {s}: {section_counts[s]} cards" for s in sorted_sections]
    lines.append(
        f"Section distribution ({num_sections} sections, avg {avg:.1f} cards each):\n"
        + "\n".join(dist_lines)
    )

    if smallest == 0 or largest / smallest > 2.0:
        biggest = max(section_counts, key=lambda s: section_counts[s])
        smallest_s = min(section_counts, key=lambda s: section_counts[s])
        lines.append(
            f"Imbalanced: section {biggest} has {largest} cards "
            f"but section {smallest_s} has only {smallest}. "
            "Redistribute cards so all sections are covered roughly equally."
        )
        severity = max(severity, 2)
    elif largest / smallest > 1.5:
        lines.append("Slightly uneven across sections — consider rebalancing.")
        severity = max(severity, 1)
    else:
        lines.append("All sections are well balanced.")

    # Check section themes alignment
    num_themes = len(game.visual_identity.section_themes)
    if num_themes == 0:
        lines.append("\nVisual identity: No section themes defined yet.")
        severity = max(severity, 1)
    elif num_themes != num_sections:
        lines.append(
            f"\nVisual identity mismatch: {num_sections} sections in cards "
            f"but {num_themes} section themes in visual_identity. "
            f"Update visual_identity.section_themes to match the number of sections."
        )
        severity = max(severity, 2)
    else:
        lines.append(
            f"\nVisual identity: {num_themes} section themes defined (matches card sections)."
        )

    return "\n".join(lines), severity


def _llm_review(cards: list[dict], config: Config) -> tuple[str, int]:
    """
    Ask Cerebras to review all cards. Returns (report_text, severity) where
    severity is 0 (all good), 1 (nit), or 2 (needs improvement).
    """
    client = Cerebras(api_key=os.environ.get("CEREBRAS_API_KEY"))

    user_message = LLM_REVIEW_USER.format(
        cards_json=json.dumps(cards, ensure_ascii=False, indent=2)
    )

    response = client.chat.completions.create(
        model=CEREBRAS_MODEL,
        messages=[
            {"role": "system", "content": LLM_REVIEW_SYSTEM},
            {"role": "user", "content": user_message},
        ],
        stream=False,
    )
    assert isinstance(response, ChatCompletionResponse)

    text = response.choices[0].message.content or "(empty response)"

    # Parse verdict from the LLM output (accept old phrasing as fallback)
    lower = text.lower()
    if _VERDICT_CHANGES_REQUESTED in lower or "needs improvement" in lower:
        severity = 2
    elif _VERDICT_NIT in lower:
        severity = 1
    else:
        severity = 0

    return text, severity


def _visual_review(cards_json_path: Path, config: Config, work_dir: WorkDir) -> str:
    """
    Render each card to PNG (via render_template + pdf_to_pngs), then run one
    vision LLM call per card checking for: text cut off, layout overflow,
    missing image, color contrast issues, and other visual defects.

    Returns a summary string of visual issues found.
    """
    raise NotImplementedError()
