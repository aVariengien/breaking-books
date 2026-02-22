from typing import ClassVar, Literal

from pydantic import Field

from ._base import Schema


class SectionCard(Schema):
    """
    One per section. It is the first card in every section — it opens the territory.

    The description is very short: a trailer for what's to come. Two or three sentences at
    most. If there is a previous section, close it in one clause — what question it answered
    or what ground it covered. Then open this one: what new question appears, what shift in
    territory happens. Don't explain everything that follows. Leave it open.

    The illustration is the visual climax of the section: a rich, saturated composition
    populated with the key symbols of the section — the recurring objects, figures, or motifs
    that will appear throughout the cards that follow. Think of it as a movie poster with all
    the characters represented. It should feel more maximalist than individual card
    illustrations — this is the one image that establishes the aesthetic identity of the
    whole section.

    Colors for this section are defined in the deck's visual identity, not on this card.
    """

    type: Literal["section"] = "section"
    title: str = Field(
        description='Section title. Format: "Section N: [Section name]". The section number must be explicit. Sentence case: only the first word of the section name and proper nouns are capitalised.'
    )
    description: str = Field(
        description="2–3 sentences max. Close previous section if any; open this one. Leave it open — don't explain everything."
    )
    illustration: str = Field(
        description="Rich, maximalist scene using the section's key symbols and motifs. English. Think movie poster."
    )
    illustration_style: str = Field(
        description="Visual style for the illustration. Pick from the style list."
    )

    templates: ClassVar[list[str]] = ["section-card.html.jinja2"]

    @classmethod
    def get_examples(cls) -> list["Schema"]:
        return [
            cls(
                section=1,
                title="Section 2: The anatomy of failure",
                description=(
                    "Section 1 asked why smart people believe wrong things — and found that conviction alone "
                    "doesn't explain it. Here the question shifts: what specific illusions keep well-meaning "
                    "people from making a difference, even when they know the problem and care deeply about it?"
                ),
                illustration=(
                    "A vast hall filled with people holding torches aloft — each flame illuminating their own "
                    "face in warm light, but the room as a whole remains dark. In the center, a single "
                    "unlit candelabra. The crowd is enormous; the darkness is complete."
                ),
                illustration_style="Baroque oil painting, chiaroscuro, dramatic shadow.",
                tag=None,
            )
        ]
