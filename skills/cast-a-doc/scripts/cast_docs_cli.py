from __future__ import annotations

import argparse
from pathlib import Path

from cast_docs_common import CONFIG_DIR, ValidationResult


def print_result(result: ValidationResult) -> None:
    for warning in result.warnings:
        print(f"warning: {warning}")
    if result.errors:
        for error in result.errors:
            print(f"error: {error}")
    else:
        print("OK")


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
