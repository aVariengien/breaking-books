"""Base class shared by all card schemas."""

from typing import ClassVar

from pydantic import BaseModel


class Schema(BaseModel):
    """
    All card schemas inherit from this.

    `templates` lists the Jinja2 template filenames that can render this schema.
    One is chosen at random at render time.
    """

    type: str  # must be set to Literal['new-type'] in all subclasses
    section: int  # 0-based section index

    templates: ClassVar[list[str]]
