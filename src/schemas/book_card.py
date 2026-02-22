from typing import ClassVar, Literal

from pydantic import Field

from ._base import Schema


class BookCard(Schema):
    """
    A cover card for the entire deck. Always the **first** card in `cards`, at `section=0`.

    Fields must be grounded in information clearly present in the book or in well-established
    public knowledge about the author. Do not extrapolate or guess. If any field is uncertain
    — especially for recent books — use null.

    This card carries no argument and is not part of the card network. It does not need
    title cross-references. It exists to orient players before the session begins.
    """

    type: Literal["book_card"] = "book_card"
    section: int = Field(default=0, description="Always 0.")
    title: str = Field(description="Full title of the book, including subtitle if any.")
    author: str = Field(description="Full name of the author(s).")
    hook: str = Field(
        description=(
            "2–3 sentences. A Goodreads-style hook: what is the book trying to do, "
            "and what angle or argument does it take to do it? "
            "Should make a player who hasn't read the book want to pick it up."
        )
    )
    author_bio: str = Field(
        description=(
            "2–3 sentences. Focus on the background that made this particular book possible: "
            "the author's expertise, lived experience, or institutional position. "
            "Do not pad with general praise. Only include what is verifiable."
        )
    )
    published_year: str | None = Field(
        default=None,
        description=(
            "Year of first publication (e.g. '2011'). "
            "Set to null if the publication date is uncertain or the book is recent enough "
            "that you cannot confidently verify it."
        ),
    )

    templates: ClassVar[str] = "book-card*.html.jinja2"

    @classmethod
    def get_examples(cls) -> list["Schema"]:
        return [
            cls(
                section=0,
                title="Thinking, Fast and Slow",
                author="Daniel Kahneman",
                hook=(
                    "Why do humans make predictably irrational decisions? Kahneman argues that "
                    "we operate through two distinct mental systems — one fast and intuitive, one "
                    "slow and deliberate — and that most of our errors come from letting the first "
                    "masquerade as the second."
                ),
                author_bio=(
                    "Kahneman is a Nobel laureate in Economics and Professor Emeritus of Psychology "
                    "at Princeton. He spent decades studying cognitive biases alongside Amos Tversky, "
                    "and this book is the culmination of that research program."
                ),
                published_year="2011",
                tag=None,
            )
        ]
