from typing import ClassVar, Literal

from pydantic import Field

from ._base import Schema


class Diagram(Schema):
    """
    Use when words aren't enough and you'd naturally reach for a whiteboard. Two triggers:

    1. The author relies on a visual metaphor that recurs throughout the pages — a loop, a
       spectrum, a layered structure — and translating it into an actual labeled image would
       make it click instantly.

    2. The structure described in prose feels loose and hard to hold in your head, and a
       visual would resolve the ambiguity.

    The diagram_prompt field is sent to a diagram-generation tool. Be precise about
    structure, elements, relationships, labels, and layout.

    Default style: simple, black lines on white background. Deviate only when the content
    strongly calls for it — a spectrum might benefit from a color gradient, a layered system
    from shading.
    """

    type: Literal["diagram"] = "diagram"
    title: str = Field(description="What the diagram shows.")
    diagram_prompt: str = Field(
        description="Detailed instructions for generating the diagram. Specify structure, elements, relationships, labels, and layout."
    )
    caption: str = Field(description="One sentence explaining what to read in the diagram.")

    templates: ClassVar[str] = "diagram*.html.jinja2"

    @classmethod
    def get_examples(cls) -> list["Schema"]:
        return [
            cls(
                section=0,
                title="The Build-Measure-Learn Loop",
                diagram_prompt=(
                    "A circular loop with three stages arranged clockwise: BUILD (top), MEASURE "
                    "(bottom-right), LEARN (bottom-left). Arrows connect each stage to the next. Inside "
                    "the loop, the word 'Ideas' sits between LEARN and BUILD, 'Product' between BUILD and "
                    "MEASURE, 'Data' between MEASURE and LEARN. Outside the loop, a second concentric ring "
                    "shows the reverse planning direction: LEARN → MEASURE → BUILD, with lighter dashed "
                    "arrows. Simple black lines on white background. No color. Clean, geometric, minimal."
                ),
                caption=(
                    "We execute the loop as Build → Measure → Learn, but we plan it in reverse: figure out "
                    "what we need to learn, then what to measure, then what to build."
                ),
                tag=None,
            )
        ]
