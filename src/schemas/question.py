from typing import ClassVar, Literal

from pydantic import Field

from ._base import Schema


class Question(Schema):
    """
    A source of tension. A question players ask and that other cards try to answer.

    Questions are often good ways to start a section or bridge between sections. A good
    question is not generic. Two flavors:

    1. The classic problematic: a tension between concepts the section has introduced.
       Only works if the player knows what every term means — so every word must be grounded
       by another card or be common knowledge.

    2. The concrete puzzle: something so specific it's almost an anecdote, requiring no
       specialized vocabulary.

    The golden rule: it has to find its answer in the rest of the cards. If it's an
    interesting question the book only tangentially addresses, scratch it. If it's a mildly
    engaging question that bridges two disconnected sets of cards, it's a lighthouse.

    Use sparingly: at most one per section.
    """

    type: Literal["question"] = "question"
    question: str = Field(
        description="The question. One or two sentences. Every word must be grounded in another card or common knowledge."
    )
    texture: str = Field(
        description="Background texture description for the image generation model. Light paper ground with a fine pattern in the section's accent color."
    )

    templates: ClassVar[list[str]] = ["question.html.jinja2"]

    @classmethod
    def get_examples(cls) -> list["Schema"]:
        return [
            cls(
                section=0,
                question=(
                    "Why is a map an instrument of power?"
                ),
                texture=(
                    "Fine topographic lines on off-white paper, drawn in the [[section's accent color]] at low opacity, thin line weight, no fill."
                ),
                tag=None,
            )
        ]
