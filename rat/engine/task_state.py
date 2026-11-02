"""Model-authored task memory; a reported completion is not a quality verdict."""
from copy import deepcopy

TASK_STATE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "goal": {"type": "string", "maxLength": 500},
        "constraints": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 12},
        "success_criteria": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 12},
        "known_facts": {"type": "array", "items": {"type": "string", "maxLength": 500}, "maxItems": 12},
        "completed": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 12},
        "remaining": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 12},
        "status": {"type": "string", "enum": ["in_progress", "needs_input", "completed"]},
    },
    "required": ["goal", "constraints", "success_criteria", "known_facts", "completed", "remaining", "status"],
}


def validate_schema(value, schema, path="arguments"):
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict) or set(value) - set(schema.get("properties", {})):
            raise ValueError(f"invalid_object:{path}")
        if set(schema.get("required", [])) - set(value):
            raise ValueError(f"missing_argument:{path}")
        for key, item in value.items():
            validate_schema(item, schema["properties"][key], path + "." + key)
    elif kind == "string":
        if not isinstance(value, str) or not value.strip() or len(value) > schema.get("maxLength", 1000):
            raise ValueError(f"invalid_string:{path}")
    elif kind in ("integer", "number"):
        import math
        valid_type = type(value) is int if kind == "integer" else type(value) in (int, float)
        if not valid_type or not math.isfinite(value) or not schema.get("minimum", -float('inf')) <= value <= schema.get("maximum", float('inf')):
            raise ValueError(f"invalid_number:{path}")
    elif kind == "boolean":
        if type(value) is not bool:
            raise ValueError(f"invalid_boolean:{path}")
    elif kind == "array":
        if not isinstance(value, list) or not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 12):
            raise ValueError(f"invalid_array:{path}")
        for item in value:
            validate_schema(item, schema["items"], path + "[]")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"invalid_choice:{path}")


def validate_task_state(state):
    validate_schema(state, TASK_STATE_SCHEMA)
    if state["status"] == "completed" and state["remaining"]:
        raise ValueError("Completed state cannot have remaining work")
    return deepcopy(state)
