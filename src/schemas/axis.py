from typing import ClassVar, Literal

from pydantic import Field

from ._base import Schema


class Axis(Schema):
    """
    A continuous dimension along which other cards can be positioned. An axis works like a
    magnetic field imposed on the section: it gives every card a direction, a position, a
    reason to be placed here rather than there.

    Use an axis only when three conditions are met:
    1. At least four cards in the section can be meaningfully ordered along it.
    2. The ordering is genuinely continuous — not two clusters with a gap, not a binary.
       If the axis is really just two poles in disguise, it's a failed axis.
    3. The positioning is debatable. Players should be able to argue about the exact placement
       of each card. If everyone immediately agrees, the axis isn't revealing anything interesting.

    The value of an axis is in precision: not 'which side does this fall on?' but 'how far
    along the spectrum is it, and why?'
    """

    type: Literal["axis"] = "axis"
    title: str = Field(description="The name of the dimension. Sentence case: only the first word and proper nouns are capitalised.")
    low_end: str = Field(description="What it means to score low. A few words.")
    high_end: str = Field(description="What it means to score high. A few words.")
    description: str = Field(
        description="Why this axis is useful. What does placing cards on it reveal?"
    )

    templates: ClassVar[str] = "axis*.html.jinja2"

    @classmethod
    def get_examples(cls) -> list["Schema"]:
        return [
            cls(
                section=0,
                title="Effectiveness",
                low_end="Low real-world change (though with maybe high moral clarity)",
                high_end="High real-world change, even at the cost of compromises.",
                description=(
                    "Many figures in this section are clearly on the right side of history, but they vary "
                    "enormously in how much they actually moved the needle. Placing cards along this axis "
                    "forces players to confront the uncomfortable gap between being right and making a "
                    "difference — and to notice what the high-impact figures (<b>Rosa Parks</b>, "
                    "<b>Clarkson</b>, <b>Rob Mather</b>, <b>Joey Savoie</b>) did differently from the "
                    "low-impact ones (<b>August Landmesser</b>, <b>Granville Sharp</b>)."
                ),
                tag=None,
            )
        ]
