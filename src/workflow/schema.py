"""Minimal JSON-schema-like validation utilities."""

from __future__ import annotations

from typing import Any


_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


def validate_schema(data: Any, schema: dict[str, Any], path: str = "$") -> None:
    schema_type = schema.get("type")
    if schema_type:
        py_type = _TYPE_MAP.get(schema_type)
        if py_type and not isinstance(data, py_type):
            raise ValueError(f"Schema type mismatch at {path}: expected {schema_type}")

    if schema_type == "object":
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        if not isinstance(data, dict):
            raise ValueError(f"Schema object mismatch at {path}")
        for key in required:
            if key not in data:
                raise ValueError(f"Missing required key '{key}' at {path}")
        for key, value in data.items():
            if key in properties:
                validate_schema(value, properties[key], path=f"{path}.{key}")
    elif schema_type == "array":
        items_schema = schema.get("items")
        if items_schema and isinstance(data, list):
            for idx, item in enumerate(data):
                validate_schema(item, items_schema, path=f"{path}[{idx}]")
