"""
Concept card schema.

When to use: highlight a single key idea, term, or principle introduced by the book.
For essays that introduce the reader to a new field, most cards will likely be concept cards.
Do NOT use for concrete examples or anecdotes — use ExampleSchema for those.
"""

from typing import Annotated, ClassVar, Literal

from pydantic import Field

from ._base import Schema


class ConceptSchema(Schema):
    type: Literal["concept"] = "concept"
    title: str
    book_quotes: Annotated[
        list[str],
        Field(
            min_length=1,
            max_length=5,
            description="Verbatim quotes from the book that build or illustrate this concept.",
        ),
    ]
    image_description: str = Field(
        description=(
            "A photographic scene (no text, no diagrams) that evokes the concept. "
            "Be specific about lighting, subject, and mood."
        )
    )
    image_path: str | None = Field(
        default=None,
        description="Path to the generated image file. Filled in after image generation; do not set manually.",
    )

    templates: ClassVar[list[str]] = [
        "concept-image-left.html.jinja2",
        "concept-image-right.html.jinja2",
    ]


# ------------------------------------------------------------------
# Examples fed to the agent prompt (fill in when ready)
# ------------------------------------------------------------------
EXAMPLES: list[ConceptSchema] = []
