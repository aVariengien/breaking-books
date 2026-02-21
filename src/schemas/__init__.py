"""All card schemas. Card is the discriminated union used throughout the codebase."""

from typing import Annotated, Union

from pydantic import Field

from .concept import ConceptSchema

# Extend this union as new schemas are added.
Card = Annotated[Union[ConceptSchema], Field(discriminator="type")]

__all__ = ["Card", "ConceptSchema"]
