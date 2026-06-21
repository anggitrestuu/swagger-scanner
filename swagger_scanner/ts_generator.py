"""Generate TypeScript interfaces from parsed schemas."""

import re
from collections import defaultdict

from .parser import Schema, SchemaProperty


DEFAULT_DATA_ONLY_EXCLUDE_PATTERNS = (
    r"^ApiError$",
    r"^ApiErrorDetail$",
    r"^ApiMeta$",
    r"^ApiResponse_",
    r"^NoData$",
)


def generate_property_comment(prop: SchemaProperty) -> str:
    """Generate comment for a property.

    Args:
        prop: SchemaProperty object

    Returns:
        Comment string or empty string
    """
    parts = []

    if prop.description:
        parts.append(normalize_comment(prop.description))

    if prop.constraints:
        parts.append(f"({', '.join(normalize_comment(c) for c in prop.constraints)})")

    if not parts:
        return ""

    return f"  // {' '.join(parts)}"


def normalize_comment(value: str) -> str:
    """Collapse multiline OpenAPI descriptions into valid TS line comments."""
    return " ".join(value.split())


def apply_any_type(type_str: str, any_type: str) -> str:
    """Replace generated `any` tokens when callers prefer a safer fallback type."""
    if any_type == "any":
        return type_str
    return re.sub(r"\bany\b", any_type, type_str)


def generate_interface(
    schema: Schema,
    prefix: str = "",
    export: bool = False,
    any_type: str = "any",
) -> str:
    """Generate TypeScript interface from schema.

    Args:
        schema: Schema object
        prefix: Prefix for interface name

    Returns:
        TypeScript interface string
    """
    keyword = "export " if export else ""

    if schema.type_str:
        type_str = apply_any_type(schema.type_str, any_type)
        return f"{keyword}type {prefix}{schema.name} = {type_str};"

    lines = [f"{keyword}interface {prefix}{schema.name} {{"]

    for prop in schema.properties:
        optional = "" if prop.required else "?"
        comment = generate_property_comment(prop)
        type_str = apply_any_type(prop.type_str, any_type)
        lines.append(f"  {prop.name}{optional}: {type_str};{comment}")

    lines.append("}")

    return "\n".join(lines)


def generate_all_interfaces(
    schemas: dict[str, Schema],
    prefix: str = "",
    export: bool = False,
    any_type: str = "any",
) -> str:
    """Generate all TypeScript interfaces.

    Args:
        schemas: Dictionary of schema names to Schema objects
        prefix: Prefix for interface names

    Returns:
        Full TypeScript interfaces string
    """
    interfaces = []

    for schema in schemas.values():
        interfaces.append(generate_interface(schema, prefix, export, any_type))

    return "\n\n".join(interfaces)


def generate_typescript_file(
    schemas: dict[str, Schema],
    prefix: str = "",
    export: bool = True,
    any_type: str = "unknown",
    header: str | None = None,
    data_only: bool = False,
) -> str:
    """Generate a complete TypeScript module from schemas."""
    sections = []

    if header:
        sections.append(header.strip())

    body_schemas = filter_data_only_schemas(schemas) if data_only else schemas
    body = generate_all_interfaces(
        dict(sorted(body_schemas.items())),
        prefix=prefix,
        export=export,
        any_type=any_type,
    )
    if body:
        sections.append(body)

    return "\n\n".join(sections).rstrip() + "\n"


def is_data_only_excluded_schema_name(name: str) -> bool:
    """Return true for common envelope/error schemas omitted from data-only files."""
    return any(re.search(pattern, name) for pattern in DEFAULT_DATA_ONLY_EXCLUDE_PATTERNS)


def filter_data_only_schemas(schemas: dict[str, Schema]) -> dict[str, Schema]:
    """Remove response envelopes and shared API metadata/error schemas."""
    return {
        name: schema
        for name, schema in schemas.items()
        if not is_data_only_excluded_schema_name(name)
    }


def singularize_stem(stem: str) -> str:
    """Singularize common English plural filename stems."""
    if stem.endswith("ies") and len(stem) > 3:
        return f"{stem[:-3]}y"
    if stem.endswith("s") and not stem.endswith("ss") and len(stem) > 1:
        return stem[:-1]
    return stem


def typescript_filename_for_tag(tag: str, filename_style: str = "tag") -> str:
    """Convert an OpenAPI tag into a TypeScript filename."""
    from .md_generator import tag_to_filename

    stem = tag_to_filename(tag)
    if filename_style == "singular":
        stem = singularize_stem(stem)
    return f"{stem}.ts"


def generate_per_tag_typescript(
    endpoints,
    schemas: dict[str, Schema],
    prefix: str = "",
    export: bool = True,
    any_type: str = "unknown",
    filename_style: str = "tag",
    header: str | None = None,
    data_only: bool = False,
) -> dict[str, str]:
    """Generate TypeScript modules per OpenAPI tag."""
    from .md_generator import get_related_schemas

    tags = defaultdict(list)
    for ep in endpoints:
        for tag in ep.tags:
            tags[tag].append(ep)

    result = {}
    for tag in sorted(tags.keys()):
        related_schemas = get_related_schemas(endpoints, tag, schemas)
        if not related_schemas:
            continue
        filename = typescript_filename_for_tag(tag, filename_style)
        result[filename] = generate_typescript_file(
            related_schemas,
            prefix=prefix,
            export=export,
            any_type=any_type,
            header=header,
            data_only=data_only,
        )

    return result
