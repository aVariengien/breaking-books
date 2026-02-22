from typing import ClassVar, Literal

from pydantic import Field

from ._base import Schema


class ExampleCard(Schema):
    """
    A story, a case study, a historical episode, a metaphor the author uses to ground an
    argument. Examples are where most of the juice of non-fiction books lies.

    Write the description like a tight news lede: who, what, and why it matters — in two
    sentences. Make it vivid. Don't drop dry names without context. A player who has never
    heard of the example should understand it entirely from the card.

    Examples should name the concepts they illustrate — reference card titles by name using
    bold. This is what makes examples load-bearing members of the network rather than
    decorative anecdotes.
    """

    type: Literal["example"] = "example"
    title: str = Field(description="Name of the example. Proper noun if there is one.")
    description: str = Field(
        description="The story, crisp. 2 sentences max. Make it vivid. Reference concepts by their card title using HTML <b>bold</b>."
    )
    illustration: str = Field(description="A scene from the story. English. No text or labels.")
    illustration_style: str = Field(
        description="Visual style for the illustration. Pick from the style list."
    )
    quote: str = Field(description="One direct quote from the book where the example is discussed.")

    templates: ClassVar[str] = "example-card*.html.jinja2"

    @classmethod
    def get_examples(cls) -> list["Schema"]:
        return [
            cls(
                section=0,
                title="Rosa Parks Was Not a Seamstress",
                description=(
                    "Rosa Parks was a trained activist, not a tired seamstress — the boycott was months "
                    "in the making, and Parks was chosen over another candidate because she was harder to smear. "
                    "The whole operation was a masterclass in <b>moral reframing</b>, the polar opposite of "
                    "the <b>Noble Loser</b>."
                ),
                illustration=(
                    "A woman sitting perfectly still on a bus seat, hands folded in her lap, while "
                    "everyone around her is in frantic motion — standing, pointing, shouting. She is "
                    "the only calm figure in the frame."
                ),
                illustration_style="Black and white photography, high contrast.",
                quote=(
                    "We planned the protest long before Mrs Parks was arrested. Strategically, the success "
                    "of Parks as the symbol of the boycott turned, in part, on obscuring her longstanding "
                    "political activity."
                ),
                tag=None,
            )
        ]
