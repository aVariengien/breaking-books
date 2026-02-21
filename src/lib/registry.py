"""Auto-discover schemas and their matching templates."""

from pathlib import Path


def get_all_schema_classes() -> list[type]:
    """Return all registered Schema subclasses (imported from src/schemas/)."""
    raise NotImplementedError()


def get_all_template_paths() -> list[Path]:
    """Return paths to all Jinja2 templates in src/templates/."""
    raise NotImplementedError()


def get_templates_for_schema(schema_class: type) -> list[Path]:
    """Return the template paths declared on a schema class's `templates` ClassVar."""
    raise NotImplementedError()


def build_schema_docs() -> str:
    """Render a markdown string describing all schemas + their fields, for the agent prompt."""
    raise NotImplementedError()
