"""Auto-discover schemas and their matching templates."""

import importlib
import pkgutil
from pathlib import Path

import schemas as schemas_pkg
from lib.constants import TEMPLATES_DIR
from schemas._base import Schema


def get_all_schema_classes() -> list[type[Schema]]:
    """Return all registered Schema subclasses (imported from src/schemas/)."""
    result: list[type[Schema]] = []
    for mod_info in pkgutil.iter_modules(schemas_pkg.__path__):
        if mod_info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"schemas.{mod_info.name}")
        for obj in vars(mod).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, Schema)
                and obj is not Schema
                and obj not in result
            ):
                result.append(obj)
    return result


def get_all_template_paths() -> list[Path]:
    """Return paths to all Jinja2 templates in src/templates/."""
    return sorted(TEMPLATES_DIR.glob("*.html.jinja2"))


def get_templates_for_schema(schema_class: type[Schema]) -> list[Path]:
    """Return template paths matching the schema's glob pattern against src/templates/."""
    return sorted(TEMPLATES_DIR.glob(schema_class.templates))
