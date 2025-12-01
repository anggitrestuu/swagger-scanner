"""Generate Markdown documentation from parsed OpenAPI."""

import re
from collections import defaultdict

from .parser import Endpoint, Schema
from .ts_generator import generate_interface


def generate_endpoints_table(endpoints: list[Endpoint], tag: str) -> str:
    """Generate Markdown table for endpoints.

    Args:
        endpoints: List of Endpoint objects
        tag: Tag to filter endpoints

    Returns:
        Markdown table string
    """
    tag_endpoints = [e for e in endpoints if tag in e.tags]

    if not tag_endpoints:
        return ""

    lines = [
        "| Method | Endpoint | Description | Request Body | Response |",
        "|--------|----------|-------------|--------------|----------|",
    ]

    for ep in tag_endpoints:
        request = f"`{ep.request_body}`" if ep.request_body else "-"
        response = f"`{ep.response}`" if ep.response else "-"
        summary = ep.summary.replace("|", "\\|").replace("\n", " ") if ep.summary else "-"

        lines.append(
            f"| {ep.method} | `{ep.path}` | {summary} | {request} | {response} |"
        )

    return "\n".join(lines)


def format_tag_name(tag: str) -> str:
    """Format tag name for display.

    Args:
        tag: Raw tag string

    Returns:
        Formatted tag name
    """
    return tag.replace("-", " ").replace("_", " ").title()


def tag_to_filename(tag: str) -> str:
    """Convert tag to filename.

    Args:
        tag: Raw tag string

    Returns:
        Filename-safe string
    """
    return tag.lower().replace(" ", "-").replace("_", "-")


def extract_schema_names(type_str: str | None) -> set[str]:
    """Extract schema names from TypeScript type string.

    Args:
        type_str: TypeScript type string (e.g., "IUserResponse[]")

    Returns:
        Set of schema names without prefix
    """
    if not type_str:
        return set()

    pattern = r"I([A-Za-z0-9_]+)"
    matches = re.findall(pattern, type_str)
    return set(matches)


def get_nested_schema_names(schema: Schema) -> set[str]:
    """Extract all schema names referenced in a schema's properties.

    Args:
        schema: Schema object to analyze

    Returns:
        Set of referenced schema names
    """
    names = set()
    for prop in schema.properties:
        names.update(extract_schema_names(prop.type_str))
    return names


def get_related_schemas(
    endpoints: list[Endpoint], tag: str, all_schemas: dict[str, Schema]
) -> dict[str, Schema]:
    """Get schemas related to endpoints in a tag (including nested references).

    Args:
        endpoints: All endpoints
        tag: Tag to filter
        all_schemas: All available schemas

    Returns:
        Dictionary of related schemas
    """
    tag_endpoints = [e for e in endpoints if tag in e.tags]

    # Initial schema names from endpoints
    to_process = set()
    for ep in tag_endpoints:
        to_process.update(extract_schema_names(ep.request_body))
        to_process.update(extract_schema_names(ep.response))

    # Recursively find all nested schemas
    processed = set()
    related = {}

    while to_process:
        name = to_process.pop()
        if name in processed:
            continue
        processed.add(name)

        if name in all_schemas:
            schema = all_schemas[name]
            related[name] = schema
            # Add nested schema references to process queue
            nested = get_nested_schema_names(schema)
            to_process.update(nested - processed)

    return related


def generate_tag_markdown(
    tag: str,
    endpoints: list[Endpoint],
    schemas: dict[str, Schema],
    prefix: str = "I",
) -> str:
    """Generate Markdown for a single tag.

    Args:
        tag: Tag name
        endpoints: All endpoints
        schemas: Related schemas for this tag
        prefix: Prefix for TypeScript interfaces

    Returns:
        Markdown content for this tag
    """
    formatted_tag = format_tag_name(tag)

    lines = [
        f"# {formatted_tag} API",
        "",
        "---",
        "",
        "## API Endpoints",
        "",
        generate_endpoints_table(endpoints, tag),
        "",
    ]

    if schemas:
        lines.extend([
            "---",
            "",
            "## TypeScript Interfaces",
            "",
            "```typescript",
        ])

        for schema in schemas.values():
            lines.append(generate_interface(schema, prefix))
            lines.append("")

        lines.append("```")

    return "\n".join(lines)


def generate_per_tag_markdown(
    openapi: dict,
    endpoints: list[Endpoint],
    schemas: dict[str, Schema],
    prefix: str = "I",
) -> dict[str, str]:
    """Generate Markdown files per tag.

    Args:
        openapi: Original OpenAPI specification
        endpoints: List of parsed endpoints
        schemas: Dictionary of parsed schemas
        prefix: Prefix for TypeScript interfaces

    Returns:
        Dictionary mapping filename to markdown content
    """
    tags = defaultdict(list)
    for ep in endpoints:
        for tag in ep.tags:
            tags[tag].append(ep)

    result = {}

    for tag in sorted(tags.keys()):
        filename = f"{tag_to_filename(tag)}.md"
        related_schemas = get_related_schemas(endpoints, tag, schemas)
        content = generate_tag_markdown(tag, endpoints, related_schemas, prefix)
        result[filename] = content

    return result


def generate_index_markdown(
    openapi: dict,
    endpoints: list[Endpoint],
) -> str:
    """Generate index/README markdown.

    Args:
        openapi: Original OpenAPI specification
        endpoints: List of parsed endpoints

    Returns:
        Index markdown content
    """
    info = openapi.get("info", {})
    title = info.get("title", "API Documentation")
    description = info.get("description", "")
    version = info.get("version", "")

    tags = defaultdict(list)
    for ep in endpoints:
        for tag in ep.tags:
            tags[tag].append(ep)

    lines = [
        f"# {title}",
        "",
    ]

    if version:
        lines.append(f"**Version:** {version}")
        lines.append("")

    if description:
        lines.append(description)
        lines.append("")

    lines.extend([
        "---",
        "",
        "## API Documentation",
        "",
        "| Module | Endpoints | File |",
        "|--------|-----------|------|",
    ])

    for tag in sorted(tags.keys()):
        formatted_tag = format_tag_name(tag)
        filename = f"{tag_to_filename(tag)}.md"
        count = len(tags[tag])
        lines.append(f"| {formatted_tag} | {count} | [{filename}](./{filename}) |")

    lines.extend([
        "",
        "---",
        "",
        f"*Total: {len(endpoints)} endpoints across {len(tags)} modules*",
    ])

    return "\n".join(lines)
