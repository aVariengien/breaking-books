from typing import ClassVar, Literal

from pydantic import Field

from ._base import Schema


class ExampleCard(Schema):
    """
    A story, a case study, a historical episode, a metaphor the author uses to ground an
    argument. Examples are where most of the juice of non-fiction books lies. They are the
    foundations that give readers the energy to invest in building a conceptual apparatus.
    Invest in them. Write the description like you would write a short story: who, what, and
    why it matters. Make it vivid. Don't drop dry names without context — add context so the
    reader knows who we are talking about. A player who has never heard of the example should
    understand it entirely from the card.

    Examples should name the concepts they illustrate. If Rosa Parks's story is the antithesis
    of the <b>Noble Loser</b>, say so on the card. This is what makes examples load-bearing
    members of the network rather than decorative anecdotes.
    """

    type: Literal["example"] = "example"
    title: str = Field(description="Name of the example. Proper noun if there is one.")
    description: str = Field(
        description="The story, crisp. ~3 sentences. Make it vivid. Reference concepts by their card title."
    )
    illustration: str = Field(description="A scene from the story. English. No text or labels.")
    illustration_style: str = Field(
        description="Visual style for the illustration. Pick from the style list."
    )
    quote: str = Field(description="One direct quote from the book where the example is discussed.")

    templates: ClassVar[list[str]] = ["example-card.html.jinja2"]

    @classmethod
    def get_examples(cls) -> list["Schema"]:
        """Return example ExampleCard instances."""
        return [
            cls(
                section=0,
                title="Rosa Parks Was Not a Seamstress",
                description=(
                    "The Montgomery bus boycott wasn't a tired seamstress acting on impulse — Rosa Parks "
                    "was a trained activist. The boycott was planned months ahead by Jo Ann Robinson and "
                    "the Women's Political Council, who printed 35,000 leaflets overnight. They chose Parks "
                    "over Claudette Colvin — an unmarried pregnant teenager the white press would have "
                    "destroyed — and the entire operation, from the icon to the legal team to the 381-day "
                    "carpool, was a masterclass in strategic moral reframing: the polar opposite of the "
                    "<b>Noble Loser</b>."
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
