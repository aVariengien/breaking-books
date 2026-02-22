from typing import ClassVar, Literal

from pydantic import Field

from ._base import Schema


class LongQuote(Schema):
    """
    A verbatim excerpt from the book, meant to be read aloud. Pick a LongQuote when the
    author's own words carry more weight than any summary could — when the prose is intricate,
    dense, almost like a poem.

    A good LongQuote is a mine — dense material you come back to. It can serve as the
    gravitational center of a section. Another reason to use a LongQuote: to show the author's
    style. A LongQuote lets the players taste the author's voice directly.

    Aim for 60–70 words — long enough to have weight, short enough to read aloud in 1 minute.
    Add one line of context so players know where in the book it sits and what it addresses.

    Aim for 1–3 per book.
    """

    type: Literal["long_quote"] = "long_quote"
    quote: str = Field(description="Verbatim. 60–70 words — meaty enough to feel like a real excerpt.")
    context: str = Field(description="One sentence: where this sits in the book and what it's about.")
    texture: str = Field(
        description="Background texture description for the image generation model. Light paper ground with a fine pattern in the section's accent color."
    )

    templates: ClassVar[list[str]] = ["long-quote.html.jinja2"]

    @classmethod
    def get_examples(cls) -> list["Schema"]:
        return [
            cls(
                section=0,
                quote=(
                    "Metamodernism is the marriage of extreme irony with a deep, unyielding sincerity. "
                    "These two sides are in superposition to one another. The sincerity makes the irony "
                    "much more effective, because it becomes genuinely ambiguous; the irony, because it is "
                    "all-encompassing, creates room for an unapologetic, even religious, sincerity of "
                    "emotions, hopes and aspirations."
                ),
                context=(
                    "Hanzi Freinacht defines metamodernism for the first time, near the end of the "
                    "introduction, after demonstrating both the irony and the sincerity on the reader."
                ),
                texture=(
                    "Two sets of thin sine waves drawn in the section's accent color on off-white paper, "
                    "running horizontally at slightly different frequencies so they overlap and interfere — "
                    "producing moments of reinforcement and moments of near-cancellation. Low opacity, fine "
                    "line weight."
                ),
                tag=None,
            )
        ]
