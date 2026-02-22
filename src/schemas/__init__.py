"""All card schemas. Card is the discriminated union used throughout the codebase."""

from typing import Annotated, Union

from pydantic import Field

from .axis import Axis
from .default import DefaultCard
from .definition import Definition
from .diagram import Diagram
from .enumeration import Enumeration, EnumerationItem
from .example import ExampleCard
from .long_quote import LongQuote
from .question import Question
from .section import SectionCard

# Extend this union as new schemas are added.
Card = Annotated[
    Union[
        Axis,
        DefaultCard,
        Definition,
        Diagram,
        Enumeration,
        ExampleCard,
        LongQuote,
        Question,
        SectionCard,
    ],
    Field(discriminator="type"),
]

__all__ = [
    "Card",
    "Axis",
    "DefaultCard",
    "Definition",
    "Diagram",
    "Enumeration",
    "EnumerationItem",
    "ExampleCard",
    "LongQuote",
    "Question",
    "SectionCard",
]
