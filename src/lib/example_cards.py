"""Build example card dicts from schema get_examples(). Used by quality tests."""

from lib.registry import get_all_schema_classes


def build_example_cards() -> dict[str, dict]:
    """Return card_type -> example card dict for each schema with get_examples()."""
    result: dict[str, dict] = {}
    for cls in get_all_schema_classes():
        type_field = cls.model_fields.get("type")
        card_type = type_field.default if type_field else None
        if card_type is None:
            continue
        examples = cls.get_examples()
        if examples:
            result[card_type] = examples[0].model_dump()
    return result
