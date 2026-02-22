from typing import ClassVar, Literal

from pydantic import BaseModel, Field

from ._base import Schema


class EnumerationItem(BaseModel):
    """A single item within an Enumeration card."""

    label: str = Field(description="The item name. A few words.")
    gloss: str = Field(
        description="What it means. As brief as the number of items demands: a sentence for 3 items, seven words for 8 items."
    )


class Enumeration(Schema):
    """
    A list that deserves to exist as a unit, where each item is too small to warrant its
    own card but the completeness of the list matters. Use it when the author explicitly
    enumerates reasons, types, steps, or causes and the list-as-a-whole is a meaningful
    structure in the book.

    Don't create an enumeration just because something is listed — only when the set is a
    structural piece of the argument.

    Each item is a short label and a brief gloss. The fewer items, the more you can say per
    item. Three items? A sentence each. Eight items? Seven words each. The card has to fit
    on a 10×15 cm card.
    """

    type: Literal["enumeration"] = "enumeration"
    title: str = Field(description="What is being enumerated.")
    description: str = Field(
        description="One sentence: what this group is and why it exists as a unit."
    )
    items: list[EnumerationItem] = Field(description="The enumerated items.")

    templates: ClassVar[str] = "enumeration*.html.jinja2"

    @classmethod
    def get_examples(cls) -> list["Schema"]:
        return [
            cls(
                section=0,
                title="Five Illusions of the Noble Loser",
                description=(
                    "Five persistent myths about how social change works, each one a trap that lets good "
                    "people feel righteous while achieving nothing."
                ),
                items=[
                    EnumerationItem(
                        label="Awareness",
                        gloss="Knowing about injustice doesn't mean you'll act on it. The belief-behaviour gap is vast.",
                    ),
                    EnumerationItem(
                        label="Good Intentions",
                        gloss="Most charities are never rigorously evaluated; 75% of those that are show small or no effects.",
                    ),
                    EnumerationItem(
                        label="Right Reasons",
                        gloss="The right thing often happens for the wrong reasons. <b>Moral reframing</b> exploits this.",
                    ),
                    EnumerationItem(
                        label="Purity",
                        gloss="Demanding total agreement from your coalition produces a movement that is 100% pure and 0% effective.",
                    ),
                    EnumerationItem(
                        label="Synergy",
                        gloss="Not all good things go together. Sometimes you have to aim lower to hit your target.",
                    ),
                ],
                tag=None,
            )
        ]
