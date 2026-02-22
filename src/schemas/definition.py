from typing import ClassVar, Literal

from pydantic import Field

from ._base import Schema


class Definition(Schema):
    """
    A dictionary entry. Use it when a word keeps coming back across many cards and its
    meaning is non-trivial — when having it defined precisely would let every subsequent
    card that uses the term land more cleanly.

    Don't overuse definitions. Only define the base-layer terms that other cards build on.
    The aesthetic is deliberate and authoritative, like a good entry in a specialized
    encyclopedia.

    Ideally, draw the etymology and usage from the book itself. If the book doesn't provide
    etymology, you can interpolate, but keep it to one sentence. The usage example should
    show the word in context — preferably a context that connects to other cards in the deck.
    """

    type: Literal["definition"] = "definition"
    word: str = Field(description="The term being defined. Word casing: only proper nouns are capitalised.")
    part_of_speech: str = Field(description="noun, verb, adjective, etc.")
    etymology: str = Field(
        description="One sentence. Where the word comes from and what it literally means."
    )
    definition: str = Field(
        description="The definition as it applies in this book. 1–2 sentences."
    )
    usage_example: str = Field(
        description="One short example sentence using the word in context from the book."
    )
    texture: str = Field(
        description="Background texture description for the image generation model. Light paper ground with a fine pattern in the section's accent color."
    )

    templates: ClassVar[list[str]] = ["definition.html.jinja2"]

    @classmethod
    def get_examples(cls) -> list["Schema"]:
        return [
            cls(
                section=0,
                word="moral reframing",
                part_of_speech="noun",
                etymology=(
                    "From moral (Latin moralis, concerning character) + reframing (re- + frame, to place "
                    "in a new structure). Literally: placing an ethical argument inside a new frame so it "
                    "lands with a different audience."
                ),
                definition=(
                    "The tactic of finding new arguments for the same standpoint — arguments that resonate "
                    "with people outside your group and fall within the <b>Overton Window</b>. You don't "
                    "change what you believe; you change which reasons you lead with, choosing the ones "
                    "your audience already cares about."
                ),
                usage_example=(
                    "Clarkson used <b>moral reframing</b> when he shifted attention from the suffering of "
                    "the enslaved to the death toll among British sailors."
                ),
                texture=(
                    "Repeating pattern of overlapping rectangular frames — nested squares and rectangles of "
                    "varying sizes, some rotated slightly — drawn in the section's accent color on off-white "
                    "paper at low opacity, thin line weight, no fill."
                ),
                tag=None,
            )
        ]
