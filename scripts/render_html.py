#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cast_docs_core import (
    CONFIG_DIR,
    load_config,
    load_json,
    print_result,
    render_html,
    validate_document,
    validate_html_profile,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a CAST Docs document JSON file to self-contained HTML.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
    parser.add_argument("--validate", action="store_true", help="Validate document JSON before render and HTML after render.")
    args = parser.parse_args()

    doc = load_json(args.input)
    if args.validate:
        doc_result = validate_document(doc, args.config_dir)
        if not doc_result.ok:
            print_result(doc_result)
            return 1

    html_text = render_html(doc, config_dir=args.config_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html_text, encoding="utf-8")
    print(f"rendered: {args.output}")

    if args.validate:
        profile = load_config("html-profile.json", args.config_dir)
        html_result = validate_html_profile(html_text, profile)
        print_result(html_result)
        return 0 if html_result.ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
