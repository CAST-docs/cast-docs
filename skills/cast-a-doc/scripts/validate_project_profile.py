#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cast_docs_core import CONFIG_DIR, CastDocsError, discover_project_profile, print_result, validate_project_profile


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a CAST Docs .cast-docs project profile.")
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--profile-dir", type=Path)
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
    args = parser.parse_args()

    try:
        profile = discover_project_profile(args.repo_root, args.profile_dir)
    except CastDocsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if profile is None:
        print(f"ERROR: project profile not found under {args.repo_root}", file=sys.stderr)
        return 1

    result = validate_project_profile(profile, args.config_dir)
    print_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
