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

    **Referencing other cards is mandatory.** Every DefaultCard description must name at least
    one other card title in bold. A description that floats in isolation — that could be
    extracted from the deck without any other card noticing — has failed.

    The description should be tight: two sentences. Name the idea and why it matters. Make
    sure every word can be understood by a player who has never read the book. If a term is
    specialized, define it inline or make sure a Definition card exists for it.
    """

    type: Literal["default"] = "default"
    title: str = Field(description="The concept, named plainly. 3–6 words. Sentence case: only the first word and proper nouns are capitalised.")
    description: str = Field(
        description="What it means and why it matters. 2 sentences max. HTML <b>bold</b> for key terms that are titles of other cards."
    )
    illustration: str = Field(
        description="Scene or metaphor that evokes the concept. English. No text or labels."
    )
    illustration_style: str = Field(
        description="Visual style for the illustration. Pick from the style list."
    )
    quote: str = Field(description="2–3 sentences quoted verbatim from the book, ~60–70 words. Should feel like as much text as the description itself.")

    templates: ClassVar[list[str]] = [
        "default-classic.html.jinja2",
        "default-split.html.jinja2",
        "default-brutal.html.jinja2",
        "default-monolith.html.jinja2",
        "default-tome.html.jinja2",
        "default-recto.html.jinja2",
    ]

    @classmethod
    def get_examples(cls) -> list["Schema"]:
        return [
            cls(
                section=0,
                title="The noble loser",
                description=(
                    "The figure who is clearly on the right side of history but changes nothing — "
                    "someone whose convictions are spotless and whose impact is zero. Each of the "
                    "<b>Five illusions of the noble loser</b> offers a different way for good people "
                    "to waste their energy while the problems they care about fester."
                ),
                illustration=(
                    "A lone figure standing on a cliff edge, arms crossed, overlooking a burning valley "
                    "below, expression resolute but body motionless."
                ),
                illustration_style="Film grain, golden hour, melancholic.",
                quote=(
                    "His open resistance was brave but futile. He had the right values and the wrong strategy — "
                    "the classic profile of the Noble Loser. Moral clarity, in the absence of political skill, "
                    "does not produce change; it produces martyrdom, which is a very different thing."
                ),
                tag=None,
            )
        ]
