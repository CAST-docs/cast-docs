#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from cast_docs_core import add_common_args, load_json, print_result, validate_document


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a CAST Docs document JSON file.")
    add_common_args(parser)
    args = parser.parse_args()

    doc = load_json(args.input)
    result = validate_document(doc, args.config_dir)
    print_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
