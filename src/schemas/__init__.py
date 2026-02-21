"""All card schemas. Card is the discriminated union used throughout the codebase."""

from typing import Annotated, Union

from pydantic import Field

from .default import DefaultCard
from .example import ExampleCard

# Extend this union as new schemas are added.
Card = Annotated[Union[DefaultCard, ExampleCard], Field(discriminator="type")]

__all__ = ["Card", "DefaultCard", "ExampleCard"]
