"""Base class shared by all card schemas."""

from typing import ClassVar, Literal

from pydantic import BaseModel, Field


class Schema(BaseModel):
    """
    All card schemas inherit from this.

    `templates` lists the Jinja2 template filenames that can render this schema.
    One is chosen at random at render time.
    """

    type: str  # must be set to Literal['new-type'] in all subclasses
    section: int = Field(description="0-based section index.")
    tag: Literal["top_end", "middle", "bottom_end"] | None = Field(
        default=None,
        description="Optional positional marker within the section.",
    )

    templates: ClassVar[str]  # glob pattern matched against src/templates/

    @classmethod
    def get_examples(cls) -> list["Schema"]:
        """Return example instances of this schema. Override in subclasses to provide examples."""
        return []
