"""Auto-discover schemas and their matching templates."""

import importlib
import pkgutil
from pathlib import Path

import schemas as schemas_pkg
from schemas._base import Schema

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_BASE_FIELD_NAMES = {"type", "section", "templates"}


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
    return sorted(_TEMPLATES_DIR.glob("*.html.jinja2"))


def get_templates_for_schema(schema_class: type[Schema]) -> list[Path]:
    """Return the template paths declared on a schema class's `templates` ClassVar."""
    return [_TEMPLATES_DIR / name for name in schema_class.templates]


def build_schema_docs() -> str:
    """Render a markdown string describing all schemas + their fields, for the agent prompt."""
    parts: list[str] = []

    for cls in get_all_schema_classes():
        type_field = cls.model_fields.get("type")
        type_val = type_field.default if type_field else "unknown"

        parts.append(f'### `{cls.__name__}` — use `"type": "{type_val}"`')
        parts.append("")

        if cls.__doc__:
            parts.append(cls.__doc__.strip())
            parts.append("")

        parts.append("**Fields** (in addition to the base `section`):")
        for name, field_info in cls.model_fields.items():
            if name in _BASE_FIELD_NAMES:
                continue
            ann = field_info.annotation
            ann_str = getattr(ann, "__name__", str(ann))
            desc = field_info.description or ""
            suffix = f" — {desc}" if desc else ""
            parts.append(f"- `{name}` ({ann_str}){suffix}")

        # Include module-level EXAMPLES if populated
        mod = importlib.import_module(cls.__module__)
        examples: list = getattr(mod, "EXAMPLES", [])
        if examples:
            parts.append("")
            parts.append("**Examples:**")
            parts.append("```json")
            import json

            for ex in examples:
                parts.append(json.dumps(ex.model_dump(), ensure_ascii=False, indent=2))
            parts.append("```")

        parts.append("")

    return "\n".join(parts)
