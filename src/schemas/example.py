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

    **Referencing other cards is mandatory.** Every ExampleCard description must name at least
    one concept card title in bold. This is what makes examples load-bearing members of the
    network rather than decorative anecdotes. An example that illustrates nothing the rest of
    the deck can point to is a dead end — cut it or rewrite it.
    """

    type: Literal["example"] = "example"
    title: str = Field(description="Name of the example. Proper noun if there is one. Sentence case: only the first word and proper nouns are capitalised.")
    description: str = Field(
        description="The story, crisp. 2 sentences max. Make it vivid. Reference concepts by their card title using HTML <b>bold</b>."
    )
    illustration: str = Field(description="A scene from the story. English. No text or labels.")
    illustration_style: str = Field(
        description="Visual style for the illustration. Pick from the style list."
    )
    quote: str = Field(description="2–3 sentences quoted verbatim from the book where the example is discussed, ~60–70 words. Should feel like as much text as the description itself.")

    templates: ClassVar[str] = "example-card*.html.jinja2"

    @classmethod
    def get_examples(cls) -> list["Schema"]:
        return [
            cls(
                section=0,
                title="Rosa Parks was not a seamstress",
                description=(
                    "Rosa Parks was a trained activist, not a tired seamstress — the boycott was months "
                    "in the making, and Parks was chosen over another candidate because she was harder to smear. "
                    "The whole operation was a masterclass in <b>moral reframing</b>, the polar opposite of "
                    "the <b>noble loser</b>."
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
