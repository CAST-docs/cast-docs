#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cast_docs_core import (
    CONFIG_DIR,
    CastDocsError,
    apply_project_profile,
    discover_project_profile,
    load_config,
    load_json,
    output_path_from_policy,
    print_result,
    render_html,
    validate_document,
    validate_html_profile,
    validate_project_profile,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a CAST Docs document JSON file to self-contained HTML.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
    parser.add_argument("--validate", action="store_true", help="Validate document JSON before render and HTML after render.")
    parser.add_argument("--repo-root", type=Path, help="Repository root for .cast-docs project profile discovery.")
    parser.add_argument("--profile-dir", type=Path, help="Explicit project profile directory inside the repository root.")
    parser.add_argument(
        "--output-policy",
        choices=("explicit", "shareable", "local"),
        default="explicit",
        help="Select output from the project profile when --output is omitted.",
    )
    args = parser.parse_args()

    try:
        profile = discover_project_profile(args.repo_root, args.profile_dir)
        if profile is not None:
            profile_result = validate_project_profile(profile, args.config_dir)
            if not profile_result.ok:
                print_result(profile_result)
                return 1

        doc = load_json(args.input)
        doc_for_validation = apply_project_profile(doc, profile)
        output = output_path_from_policy(args.output, doc_for_validation, profile, args.output_policy)
    except CastDocsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.validate:
        doc_result = validate_document(doc_for_validation, args.config_dir)
        if not doc_result.ok:
            print_result(doc_result)
            return 1

    html_text = render_html(doc, config_dir=args.config_dir, profile=profile)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_text, encoding="utf-8")
    print(f"rendered: {output}")

    if args.validate:
        profile = load_config("html-profile.json", args.config_dir)
        html_result = validate_html_profile(html_text, profile)
        print_result(html_result)
        return 0 if html_result.ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
