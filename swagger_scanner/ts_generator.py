"""Generate TypeScript interfaces from parsed schemas."""

from .parser import Schema, SchemaProperty


def generate_property_comment(prop: SchemaProperty) -> str:
    """Generate comment for a property.

    Args:
        prop: SchemaProperty object

    Returns:
        Comment string or empty string
    """
    parts = []

    if prop.description:
        parts.append(prop.description)

    if prop.constraints:
        parts.append(f"({', '.join(prop.constraints)})")

    if not parts:
        return ""

    return f"  // {' '.join(parts)}"


def generate_interface(schema: Schema, prefix: str = "I") -> str:
    """Generate TypeScript interface from schema.

    Args:
        schema: Schema object
        prefix: Prefix for interface name

    Returns:
        TypeScript interface string
    """
    lines = [f"interface {prefix}{schema.name} {{"]

    for prop in schema.properties:
        optional = "" if prop.required else "?"
        comment = generate_property_comment(prop)
        lines.append(f"  {prop.name}{optional}: {prop.type_str};{comment}")

    lines.append("}")

    return "\n".join(lines)


def generate_all_interfaces(
    schemas: dict[str, Schema], prefix: str = "I"
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
        interfaces.append(generate_interface(schema, prefix))

    return "\n\n".join(interfaces)
