"""Tests for build_schema_docs() in big_prompt.py."""

from big_prompt import build_schema_docs
from lib.registry import get_all_schema_classes


def test_build_schema_docs_runs():
    result = build_schema_docs()
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_schema_docs_contains_all_schema_types():
    result = build_schema_docs()
    for cls in get_all_schema_classes():
        type_val = cls.model_fields["type"].default
        assert cls.__name__ in result, f"Missing schema class name: {cls.__name__}"
        assert type_val in result, f"Missing type value: {type_val}"


def test_build_schema_docs_contains_all_field_names():
    result = build_schema_docs()
    for cls in get_all_schema_classes():
        for field_name in cls.model_fields:
            assert field_name in result, f"Missing field '{field_name}' from {cls.__name__}"


def test_build_schema_docs_covers_known_schemas():
    classes = get_all_schema_classes()
    names = {cls.__name__ for cls in classes}
    assert "DefaultCard" in names
    assert "ExampleCard" in names
