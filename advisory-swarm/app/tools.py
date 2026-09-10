"""Merges every specialist's tools into one identical, sorted-by-name list.

Every specialist gets the SAME tool list (scoped by persona instruction, not by a private tool
set) — this is what the Design Document's prompt-caching section requires for a stable prefix.
We're not implementing the caching itself for the demo (time), but keeping the list unified
costs nothing and keeps this file correct if caching gets added later.
"""

from specialists import SPECIALISTS


def _build():
    schemas_by_name = {}
    impls = {}
    for spec in SPECIALISTS:
        for schema in spec["tool_schemas"]:
            name = schema["name"]
            if name in schemas_by_name and schemas_by_name[name] != schema:
                raise ValueError(f"tool name collision with different schema: {name!r}")
            schemas_by_name[name] = schema
        for name, fn in spec["tool_impls"].items():
            impls[name] = fn
    sorted_schemas = [schemas_by_name[name] for name in sorted(schemas_by_name)]
    return sorted_schemas, impls


ALL_TOOL_SCHEMAS, ALL_TOOL_IMPLS = _build()
