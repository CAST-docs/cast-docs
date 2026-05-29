#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from cast_docs_core import ROOT, load_json


SCHEMA_PATH = ROOT / "schemas" / "doc.schema.json"
REQUIRED_DEFS = {
    "manifest",
    "section",
    "block",
    "diagramBlock",
    "svgDiagramSource",
    "localizedString",
    "inlineText",
}


def main() -> int:
    schema = load_json(SCHEMA_PATH)
    errors: list[str] = []

    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("schema must declare JSON Schema draft 2020-12")
    if schema.get("type") != "object":
        errors.append("schema root must be an object")

    defs = schema.get("$defs")
    if not isinstance(defs, dict):
        errors.append("schema must contain $defs")
        defs = {}

    missing = sorted(REQUIRED_DEFS - set(defs))
    if missing:
        errors.append(f"schema is missing required definitions: {', '.join(missing)}")

    svg_source = defs.get("svgDiagramSource")
    if isinstance(svg_source, dict):
        properties = svg_source.get("properties")
        content = properties.get("content") if isinstance(properties, dict) else None
        if not isinstance(content, dict) or content.get("type") != "string":
            errors.append("svgDiagramSource.content must remain a structural string field")
    else:
        errors.append("schema $defs.svgDiagramSource must be an object")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("schema contract ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
