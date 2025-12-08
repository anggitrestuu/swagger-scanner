"""CLI entry point for Swagger Scanner."""

import os
import sys

import click

from .fetcher import fetch_openapi
from .md_generator import generate_index_markdown, generate_per_tag_markdown
from .parser import parse_endpoints, parse_schemas


@click.command()
@click.argument("url")
@click.option(
    "-o",
    "--output",
    default="./docs",
    help="Output directory path (default: ./docs)",
)
@click.option(
    "-p",
    "--prefix",
    default="I",
    help="Prefix for TypeScript interfaces (default: I)",
)
def main(url: str, output: str, prefix: str) -> None:
    """Scan OpenAPI v3 JSON and generate Markdown documentation.

    URL is the endpoint to fetch OpenAPI JSON from (e.g., http://localhost:8000/openapi.json)

    Output will be a directory with one file per tag, plus an index.md file.
    """
    click.echo(f"Fetching OpenAPI spec from {url}...")

    try:
        openapi = fetch_openapi(url)
    except Exception as e:
        click.echo(f"Error fetching OpenAPI spec: {e}", err=True)
        sys.exit(1)

    info = openapi.get("info", {})
    title = info.get("title", "Unknown API")
    version = info.get("version", "unknown")
    click.echo(f"Parsing: {title} (v{version})")

    endpoints, inline_schemas = parse_endpoints(openapi, prefix)
    click.echo(f"Found {len(endpoints)} endpoints")

    schemas = parse_schemas(openapi, prefix)
    click.echo(f"Found {len(schemas)} schemas")

    # Merge inline schemas with component schemas
    all_schemas = {**schemas, **inline_schemas}
    if inline_schemas:
        click.echo(f"Found {len(inline_schemas)} inline schemas")

    os.makedirs(output, exist_ok=True)

    tag_files = generate_per_tag_markdown(openapi, endpoints, all_schemas, prefix)
    for filename, content in tag_files.items():
        filepath = os.path.join(output, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        click.echo(f"  Created: {filepath}")

    index_content = generate_index_markdown(openapi, endpoints)
    index_path = os.path.join(output, "index.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_content)
    click.echo(f"  Created: {index_path}")

    click.echo(f"\nDocumentation written to {output}/ ({len(tag_files) + 1} files)")


if __name__ == "__main__":
    main()
