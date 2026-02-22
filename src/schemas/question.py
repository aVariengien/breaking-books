from typing import ClassVar, Literal

from pydantic import Field

from ._base import Schema


class Question(Schema):
    """
    A question that players will argue over and that the section's cards work to answer.

    **The standard:** could a smart person answer this without reading the book? If yes,
    it's too generic. A good question requires the book's specific argument to answer —
    it opens a gap that only the cards can close.

    **Write it like a riddle.** Ground it in something concrete — an object, a name, a
    mechanism, a number, a counterintuitive gap. Start from something you can point to.

    Good: "Why is a map an instrument of power?" — everyday object, attached to a claim.
    Good: "What separates a pivot from quitting?" 
    Bad: "If most people agree a problem is worth solving, why does so little change?" - it feels like a rethorical question
    Bad: "How do organizations resist change?" — textbook survey question.

    **The golden rule:** the question must find its answer in the other cards of the section.
    If the deck can't answer it, cut it.

    Use sparingly: at most one per section.
    """

    type: Literal["question"] = "question"
    question: str = Field(
        description="One sharp sentence. Concrete noun or gap, not an abstraction. No jargon that isn't grounded in another card."
    )
    texture: str = Field(
        description="Background texture description for the image generation model. Light paper ground with a fine pattern in the section's accent color."
    )

    templates: ClassVar[str] = "question*.html.jinja2"

    @classmethod
    def get_examples(cls) -> list["Schema"]:
        return [
            cls(
                section=0,
<<<<<<< HEAD
                question="Why is a map an instrument of power?",
=======
                question=("Why is a map an instrument of power?"),
>>>>>>> 92f3ef9f3eb99f2c002c7ab9b9f7fbc8d5cefab2
                texture=(
                    "Fine topographic lines on off-white paper, drawn in the [[section's accent color]] at low opacity, thin line weight, no fill."
                ),
                tag=None,
            ),
            cls(
                section=0,
                question="What separates a pivot from quitting?",
                texture=(
                    "Repeating pattern of small outline arrows — straight, forked, curved back — scattered on off-white paper, drawn in the [[section's accent color]] at low opacity, thin line weight, no fill."
                ),
                tag=None,
            ),
        ]
