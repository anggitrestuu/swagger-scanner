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

    # Sort by path, then by method for consistent ordering
    tag_endpoints.sort(key=lambda e: (e.path, e.method))

    lines = [
        "| Method | Endpoint | Description | Parameters | Request Body | Response |",
        "|--------|----------|-------------|------------|--------------|----------|",
    ]

    for ep in tag_endpoints:
        params = f"`{ep.parameters}`" if ep.parameters else "-"
        request = f"`{ep.request_body}`" if ep.request_body else "-"
        response = f"`{ep.response}`" if ep.response else "-"
        summary = ep.summary.replace("|", "\\|").replace("\n", " ") if ep.summary else "-"

        lines.append(
            f"| {ep.method} | `{ep.path}` | {summary} | {params} | {request} | {response} |"
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


def tag_search_terms(tag: str) -> set[str]:
    """Build simple searchable words for a tag name."""
    terms = {
        part.lower()
        for part in re.split(r"[^A-Za-z0-9]+", tag)
        if len(part) >= 4
    }

    expanded = set(terms)
    for term in terms:
        if term.endswith("ies") and len(term) > 4:
            expanded.add(f"{term[:-3]}y")
        if term.endswith("s") and len(term) > 4:
            expanded.add(term[:-1])

    return expanded


def collect_tag_context_text(
    tag: str, endpoints: list[Endpoint], schemas: dict[str, Schema]
) -> str:
    """Collect searchable text for finding likely cross-module references."""
    parts = []

    for ep in endpoints:
        if tag not in ep.tags:
            continue
        parts.extend(
            [
                ep.path,
                ep.summary,
                ep.operation_id,
                ep.parameters or "",
                ep.request_body or "",
                ep.response or "",
            ]
        )

    for schema in schemas.values():
        parts.append(schema.name)
        for prop in schema.properties:
            parts.extend([prop.name, prop.type_str, prop.description])

    return " ".join(part for part in parts if part).lower()


def find_related_tags(
    tag: str,
    endpoints: list[Endpoint],
    schemas: dict[str, Schema],
    all_tags: list[str],
) -> list[str]:
    """Find likely related tags mentioned by the current tag's endpoints/schemas."""
    context = collect_tag_context_text(tag, endpoints, schemas)
    related = []

    for candidate in sorted(all_tags):
        if candidate == tag:
            continue

        terms = tag_search_terms(candidate)
        if any(re.search(rf"\b{re.escape(term)}\b", context) for term in terms):
            related.append(candidate)

    return related


def generate_ai_context_block(
    tag: str,
    endpoints: list[Endpoint],
    schemas: dict[str, Schema],
    all_tags: list[str],
) -> str:
    """Generate a short context note for AI-assisted coding."""
    lines = [
        "## AI Coding Context",
        "",
        (
            f"This file only documents the `{format_tag_name(tag)}` API module. "
            "For the full API map and other available modules, start from "
            "[index.md](./index.md)."
        ),
        "",
    ]

    related_tags = find_related_tags(tag, endpoints, schemas, all_tags)
    if related_tags:
        links = [
            f"[{format_tag_name(related)}](./{tag_to_filename(related)}.md)"
            for related in related_tags
        ]
        lines.extend([
            f"Potential related API files: {', '.join(links)}.",
            "",
        ])

    module_links = [
        f"[{format_tag_name(module)}](./{tag_to_filename(module)}.md)"
        for module in sorted(all_tags)
        if module != tag
    ]
    if module_links:
        lines.extend([
            f"Other API modules: {', '.join(module_links)}.",
            "",
        ])

    return "\n".join(lines)


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
        to_process.update(extract_schema_names(ep.parameters))
        to_process.update(extract_schema_names(ep.request_body))
        to_process.update(extract_schema_names(ep.response))

    # Recursively find all nested schemas
    processed = set()
    related = {}

    while to_process:
        # Process in sorted order for deterministic output
        name = sorted(to_process)[0]
        to_process.remove(name)
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
    all_tags: list[str],
    prefix: str = "I",
) -> str:
    """Generate Markdown for a single tag.

    Args:
        tag: Tag name
        endpoints: All endpoints
        schemas: Related schemas for this tag
        all_tags: All tag names in the OpenAPI spec
        prefix: Prefix for TypeScript interfaces

    Returns:
        Markdown content for this tag
    """
    formatted_tag = format_tag_name(tag)

    lines = [
        f"# {formatted_tag} API",
        "",
        generate_ai_context_block(tag, endpoints, schemas, all_tags),
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

        for schema_name in sorted(schemas.keys()):
            lines.append(generate_interface(schemas[schema_name], prefix))
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
        content = generate_tag_markdown(
            tag, endpoints, related_schemas, sorted(tags.keys()), prefix
        )
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
        "## AI Coding Context",
        "",
        (
            "Use this index as the starting point when giving API docs to an AI coding "
            "assistant. Individual module files only document one API area, so include "
            "this file when a feature may need endpoints from another module."
        ),
        "",
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
