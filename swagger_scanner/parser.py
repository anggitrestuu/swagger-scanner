"""Parse OpenAPI v3 schema."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchemaProperty:
    """Represents a property in a schema."""

    name: str
    type_str: str
    required: bool
    description: str
    constraints: list[str] = field(default_factory=list)


@dataclass
class Schema:
    """Represents an OpenAPI schema/component."""

    name: str
    properties: list[SchemaProperty] = field(default_factory=list)


@dataclass
class Endpoint:
    """Represents an API endpoint."""

    method: str
    path: str
    operation_id: str
    summary: str
    tags: list[str]
    request_body: str | None
    response: str | None


def resolve_ref(openapi: dict, ref: str) -> dict:
    """Resolve a $ref to its actual schema.

    Args:
        openapi: Full OpenAPI specification
        ref: Reference string (e.g., "#/components/schemas/User")

    Returns:
        Resolved schema dictionary
    """
    if not ref.startswith("#/"):
        return {}

    parts = ref[2:].split("/")
    result = openapi
    for part in parts:
        result = result.get(part, {})
    return result


def sanitize_name(name: str) -> str:
    """Sanitize schema name for TypeScript.

    Args:
        name: Raw schema name

    Returns:
        Sanitized name valid for TypeScript
    """
    return name.replace("-", "_").replace(" ", "_")


def get_ref_name(ref: str) -> str:
    """Extract schema name from $ref.

    Args:
        ref: Reference string (e.g., "#/components/schemas/User")

    Returns:
        Schema name (e.g., "User")
    """
    return sanitize_name(ref.split("/")[-1])


def find_matching_schema(inline_schema: dict, openapi: dict) -> str | None:
    """Try to find a matching schema from components for an inline schema.

    Args:
        inline_schema: Inline schema object with properties
        openapi: Full OpenAPI specification

    Returns:
        Schema name if found, None otherwise
    """
    if not isinstance(inline_schema, dict):
        return None

    inline_props = set(inline_schema.get("properties", {}).keys())
    inline_required = set(inline_schema.get("required", []))

    if not inline_props:
        return None

    schemas = openapi.get("components", {}).get("schemas", {})

    for name, schema_def in schemas.items():
        schema_props = set(schema_def.get("properties", {}).keys())
        schema_required = set(schema_def.get("required", []))

        # Match by required fields and properties
        if inline_required and schema_required:
            if inline_required == schema_required and inline_props == schema_props:
                return name
        elif inline_props == schema_props:
            return name

    return None


def openapi_type_to_ts(
    schema: dict | bool | None, openapi: dict, prefix: str = "I"
) -> str:
    """Convert OpenAPI type to TypeScript type string.

    Args:
        schema: OpenAPI schema dictionary, boolean, or None
        openapi: Full OpenAPI specification (for resolving refs)
        prefix: Prefix for interface names

    Returns:
        TypeScript type string
    """
    if schema is None:
        return "any"

    if isinstance(schema, bool):
        return "any" if schema else "never"

    if not isinstance(schema, dict):
        return "any"

    if "$ref" in schema:
        return f"{prefix}{get_ref_name(schema['$ref'])}"

    if "allOf" in schema:
        types = [openapi_type_to_ts(s, openapi, prefix) for s in schema["allOf"]]
        return " & ".join(types)

    if "oneOf" in schema:
        types = [openapi_type_to_ts(s, openapi, prefix) for s in schema["oneOf"]]
        return " | ".join(types)

    if "anyOf" in schema:
        types = []
        has_null = False
        for s in schema["anyOf"]:
            if isinstance(s, dict) and s.get("type") == "null":
                has_null = True
            else:
                types.append(openapi_type_to_ts(s, openapi, prefix))
        if not types:
            return "null" if has_null else "any"
        result = " | ".join(types)
        if has_null:
            result = f"{result} | null"
        return result

    schema_type = schema.get("type", "any")

    # Handle OpenAPI 3.1 nullable types: ["string", "null"]
    is_nullable = False
    if isinstance(schema_type, list):
        if "null" in schema_type:
            is_nullable = True
            non_null_types = [t for t in schema_type if t != "null"]
            schema_type = non_null_types[0] if non_null_types else "any"
        else:
            schema_type = schema_type[0] if schema_type else "any"

    def maybe_nullable(t: str) -> str:
        return f"{t} | null" if is_nullable else t

    if "enum" in schema:
        enum_values = schema["enum"]
        result = " | ".join(f'"{v}"' for v in enum_values)
        return maybe_nullable(result)

    if schema_type == "string":
        return maybe_nullable("string")
    elif schema_type == "integer" or schema_type == "number":
        return maybe_nullable("number")
    elif schema_type == "boolean":
        return maybe_nullable("boolean")
    elif schema_type == "array":
        items = schema.get("items", {})
        # Try to find matching schema for inline object items
        if isinstance(items, dict) and items.get("type") == "object" and items.get("properties"):
            matched = find_matching_schema(items, openapi)
            if matched:
                return maybe_nullable(f"{prefix}{sanitize_name(matched)}[]")
        item_type = openapi_type_to_ts(items, openapi, prefix)
        return maybe_nullable(f"{item_type}[]")
    elif schema_type == "object":
        additional = schema.get("additionalProperties")
        if additional:
            value_type = openapi_type_to_ts(additional, openapi, prefix)
            return maybe_nullable(f"Record<string, {value_type}>")
        # Try to find matching schema for inline object
        if schema.get("properties"):
            matched = find_matching_schema(schema, openapi)
            if matched:
                return maybe_nullable(f"{prefix}{sanitize_name(matched)}")
        return maybe_nullable("object")
    else:
        return maybe_nullable("any")


def get_schema_from_content(content: dict, openapi: dict, prefix: str = "I") -> str | None:
    """Extract schema type from content object.

    Args:
        content: Content object from request body or response
        openapi: Full OpenAPI specification
        prefix: Prefix for interface names

    Returns:
        TypeScript type string or None
    """
    if not content:
        return None

    for media_type in ["application/json", "*/*"]:
        if media_type in content:
            schema = content[media_type].get("schema", {})
            if schema:
                return openapi_type_to_ts(schema, openapi, prefix)

    first_content = next(iter(content.values()), {})
    schema = first_content.get("schema", {})
    if schema:
        return openapi_type_to_ts(schema, openapi, prefix)

    return None


def parse_endpoints(openapi: dict, prefix: str = "I") -> list[Endpoint]:
    """Parse all endpoints from OpenAPI specification.

    Args:
        openapi: OpenAPI specification dictionary
        prefix: Prefix for interface names

    Returns:
        List of Endpoint objects
    """
    endpoints = []
    paths = openapi.get("paths", {})

    for path, path_item in paths.items():
        for method in ["get", "post", "put", "patch", "delete", "options", "head"]:
            if method not in path_item:
                continue

            operation = path_item[method]
            operation_id = operation.get("operationId", "")
            summary = operation.get("summary", operation.get("description", ""))
            tags = operation.get("tags", ["default"])

            request_body = None
            if "requestBody" in operation:
                content = operation["requestBody"].get("content", {})
                request_body = get_schema_from_content(content, openapi, prefix)

            response = None
            responses = operation.get("responses", {})
            for status_code in ["200", "201", "default"]:
                if status_code in responses:
                    content = responses[status_code].get("content", {})
                    response = get_schema_from_content(content, openapi, prefix)
                    if response:
                        break

            endpoints.append(
                Endpoint(
                    method=method.upper(),
                    path=path,
                    operation_id=operation_id,
                    summary=summary,
                    tags=tags,
                    request_body=request_body,
                    response=response,
                )
            )

    return endpoints


def build_constraints(prop_schema: dict) -> list[str]:
    """Build constraint descriptions from schema.

    Args:
        prop_schema: Property schema dictionary

    Returns:
        List of constraint strings
    """
    constraints = []

    if "minLength" in prop_schema:
        constraints.append(f"min length: {prop_schema['minLength']}")
    if "maxLength" in prop_schema:
        constraints.append(f"max length: {prop_schema['maxLength']}")
    if "minimum" in prop_schema:
        constraints.append(f"min: {prop_schema['minimum']}")
    if "maximum" in prop_schema:
        constraints.append(f"max: {prop_schema['maximum']}")
    if "pattern" in prop_schema:
        constraints.append(f"pattern: {prop_schema['pattern']}")
    if "format" in prop_schema:
        constraints.append(prop_schema["format"])
    if "default" in prop_schema:
        constraints.append(f"default: {prop_schema['default']}")

    return constraints


def parse_schema(
    name: str, schema_def: dict, openapi: dict, prefix: str = "I"
) -> Schema:
    """Parse a single schema definition.

    Args:
        name: Schema name
        schema_def: Schema definition dictionary
        openapi: Full OpenAPI specification
        prefix: Prefix for interface names

    Returns:
        Schema object
    """
    properties = []
    required_fields = set(schema_def.get("required", []))

    all_props = schema_def.get("properties", {})

    if "allOf" in schema_def:
        for sub_schema in schema_def["allOf"]:
            if "$ref" in sub_schema:
                resolved = resolve_ref(openapi, sub_schema["$ref"])
                all_props.update(resolved.get("properties", {}))
                required_fields.update(resolved.get("required", []))
            else:
                all_props.update(sub_schema.get("properties", {}))
                required_fields.update(sub_schema.get("required", []))

    for prop_name, prop_schema in all_props.items():
        ts_type = openapi_type_to_ts(prop_schema, openapi, prefix)

        nullable = prop_schema.get("nullable", False)
        if nullable and "null" not in ts_type:
            ts_type = f"{ts_type} | null"

        constraints = build_constraints(prop_schema)
        description = prop_schema.get("description", "")

        properties.append(
            SchemaProperty(
                name=prop_name,
                type_str=ts_type,
                required=prop_name in required_fields,
                description=description,
                constraints=constraints,
            )
        )

    return Schema(name=name, properties=properties)


def parse_schemas(openapi: dict, prefix: str = "I") -> dict[str, Schema]:
    """Parse all schemas from OpenAPI specification.

    Args:
        openapi: OpenAPI specification dictionary
        prefix: Prefix for interface names

    Returns:
        Dictionary mapping schema names to Schema objects
    """
    schemas = {}
    components = openapi.get("components", {})
    schema_defs = components.get("schemas", {})

    for name, schema_def in schema_defs.items():
        sanitized = sanitize_name(name)
        schemas[sanitized] = parse_schema(sanitized, schema_def, openapi, prefix)

    return schemas
