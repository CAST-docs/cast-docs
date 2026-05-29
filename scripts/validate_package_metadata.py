#!/usr/bin/env python3
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from cast_docs_core import ROOT


def main() -> int:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    with (ROOT / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    project = pyproject.get("project", {})

    errors: list[str] = []
    if project.get("name") != "cast-a-doc":
        errors.append("pyproject project.name must be cast-a-doc")
    if project.get("version") != version:
        errors.append("pyproject project.version must match VERSION")
    if project.get("requires-python") != ">=3.9":
        errors.append("pyproject requires-python must match the README runtime requirement")
    if project.get("dependencies") != []:
        errors.append("pyproject dependencies must stay empty unless runtime dependencies are intentionally added")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("package metadata ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
