#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from cast_docs_core import CONFIG_DIR, load_config, print_result, validate_html_profile


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a rendered CAST Docs HTML file.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--config-dir", default=CONFIG_DIR)
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as handle:
        html_text = handle.read()
    profile = load_config("html-profile.json", args.config_dir)
    result = validate_html_profile(html_text, profile)
    print_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
