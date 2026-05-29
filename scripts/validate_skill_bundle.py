#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from cast_docs_core import ROOT


BUNDLE_DIR = ROOT / "skills" / "cast-a-doc"
EXCLUDED_BUNDLE_PATHS = {
    Path("SKILL.md"),
}
EXCLUDED_ROOT_PATHS = {
    Path("scripts/validate_skill_bundle.py"),
}
EXCLUDED_DIR_NAMES = {"__pycache__"}


def same_bytes(left: Path, right: Path) -> bool:
    return left.read_bytes() == right.read_bytes()


def main() -> int:
    errors: list[str] = []
    if not BUNDLE_DIR.is_dir():
        errors.append(f"skill bundle not found: {BUNDLE_DIR}")
    else:
        bundle_files = (
            path
            for path in BUNDLE_DIR.rglob("*")
            if path.is_file() and not set(path.relative_to(BUNDLE_DIR).parts) & EXCLUDED_DIR_NAMES
        )
        for bundle_file in sorted(bundle_files):
            relative_path = bundle_file.relative_to(BUNDLE_DIR)
            if relative_path in EXCLUDED_BUNDLE_PATHS:
                continue
            root_file = ROOT / relative_path
            if not root_file.is_file():
                errors.append(f"{relative_path}: root counterpart is missing")
            elif not same_bytes(root_file, bundle_file):
                errors.append(f"{relative_path}: differs from root counterpart")

        for root_module in sorted((ROOT / "scripts").glob("cast_docs*.py")):
            relative_path = root_module.relative_to(ROOT)
            if relative_path in EXCLUDED_ROOT_PATHS:
                continue
            bundle_module = BUNDLE_DIR / "scripts" / root_module.name
            if not bundle_module.is_file():
                errors.append(f"scripts/{root_module.name}: missing from skill bundle")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("skill bundle ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
