from swagger_scanner.parser import openapi_type_to_ts, parse_schemas
from swagger_scanner.ts_generator import generate_typescript_file


def test_additional_properties_empty_schema_generates_record_alias():
    openapi = {
        "components": {
            "schemas": {
                "DynamicPayload": {
                    "type": "object",
                    "additionalProperties": {},
                }
            }
        }
    }

    schemas = parse_schemas(openapi)

    assert schemas["DynamicPayload"].type_str == "Record<string, any>"
    assert (
        generate_typescript_file(schemas)
        == "export type DynamicPayload = Record<string, unknown>;\n"
    )


def test_additional_properties_true_generates_record_type():
    schema = {
        "type": "object",
        "additionalProperties": True,
    }

    assert openapi_type_to_ts(schema, {}) == "Record<string, any>"


def test_additional_properties_false_remains_object_interface():
    openapi = {
        "components": {
            "schemas": {
                "ClosedPayload": {
                    "type": "object",
                    "additionalProperties": False,
                }
            }
        }
    }

    schemas = parse_schemas(openapi)

    assert schemas["ClosedPayload"].type_str is None
    assert generate_typescript_file(schemas) == "export interface ClosedPayload {\n}\n"
