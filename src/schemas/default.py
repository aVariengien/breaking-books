from typing import ClassVar, Literal

from pydantic import Field

from ._base import Schema


class DefaultCard(Schema):
    """
    The bread and butter of the deck. A concept the author develops, a claim they make,
    a mechanism they describe. One idea per card.

    DefaultCards and ExampleCards are the bricks from which the book's argument is unfolded.
    They need to be thought of as a whole, so they talk to each other. The simplest way to
    make them talk is to mention the titles of other cards in the description — treat bolded
    terms as signals to the player that another card exists with that name. If you'd naturally
    bold a word in a textbook, bold it here.

    The description should be tight and clear but not skeletal — roughly three sentences that
    together give a reader enough to understand the idea and feel its weight. Make sure every
    word in the description can be understood by a player who has never read the book. If a
    term is specialized, either define it inline or make sure there is a Definition card for it.
    """

    type: Literal["default"] = "default"
    title: str = Field(description="The concept, named plainly. 3–6 words.")
    description: str = Field(
        description="What it means and why it matters. ~3 sentences. HTML <b>bold</b> for key terms that are titles of other cards."
    )
    illustration: str = Field(
        description="Scene or metaphor that evokes the concept. English. No text or labels."
    )
    illustration_style: str = Field(
        description="Visual style for the illustration. Pick from the style list."
    )
    quote: str = Field(description="One direct quote from the book.")

    templates: ClassVar[list[str]] = ["default-card.html.jinja2"]


EXAMPLES: list[DefaultCard] = [
    DefaultCard(
        section=0,
        title="The Noble Loser",
        description=(
            "The figure who is clearly on the right side of history but achieves nothing in "
            "the here and now. Someone whose convictions are spotless, whose awareness is high, "
            "but who falls into the trap of believing that being right is the same as making a "
            "difference. The five traps that create Noble Losers — the <b>illusion of awareness</b>, "
            "of good intentions, of right reasons, of <b>purity</b>, and of synergy — each offer a "
            "different way for good people to waste their energy while the problems they care about fester."
        ),
        illustration=(
            "A lone figure standing on a cliff edge, arms crossed, overlooking a burning valley "
            "below, expression resolute but body motionless."
        ),
        illustration_style="Film grain, golden hour, melancholic.",
        quote="His open resistance was brave but futile.",
        tag=None,
    )
]
