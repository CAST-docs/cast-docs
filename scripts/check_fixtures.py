#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from cast_docs_core import (
    CONFIG_DIR,
    ROOT,
    load_config,
    load_json,
    render_html,
    validate_document,
    validate_html_profile,
)
from visual_lint import StyleParser, lint_css


def expected_html_path(source: Path) -> Path:
    if source.parent.name == "site":
        if source.name == "landing.json":
            return ROOT / "index.html"
        if source.name == "install.json":
            return ROOT / "install.html"
    return source.with_suffix(".html")


def collect_sources() -> list[Path]:
    sources = sorted((ROOT / "examples").glob("*.json"))
    sources.extend(sorted((ROOT / "site").glob("*.json")))
    return sources


def lint_rendered_html(html_text: str, path: Path) -> list[str]:
    parser = StyleParser()
    parser.feed(html_text)
    if not parser.styles:
        return [f"{path}: no inline style block found"]
    return lint_css("\n".join(parser.styles), path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CAST Docs fixtures and detect stale rendered HTML.")
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
    parser.add_argument(
        "--update",
        action="store_true",
        help="Rewrite checked-in HTML artifacts from their JSON sources.",
    )
    args = parser.parse_args()

    errors: list[str] = []
    profile = load_config("html-profile.json", args.config_dir)
    sources = collect_sources()

    with tempfile.TemporaryDirectory(prefix="cast-docs-fixtures.") as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        for source in sources:
            try:
                doc = load_json(source)
                doc_result = validate_document(doc, args.config_dir)
                if not doc_result.ok:
                    errors.extend(f"{source}: {error}" for error in doc_result.errors)
                    continue

                rendered = render_html(doc, config_dir=args.config_dir)
                html_result = validate_html_profile(rendered, profile)
                if not html_result.ok:
                    errors.extend(f"{source}: rendered HTML: {error}" for error in html_result.errors)
                    continue
                target = expected_html_path(source)
                visual_errors = lint_rendered_html(rendered, target)
                if visual_errors:
                    errors.extend(visual_errors)
                    continue

                if args.update:
                    target.write_text(rendered, encoding="utf-8")
                    continue

                scratch = tmp_dir / target.name
                scratch.write_text(rendered, encoding="utf-8")
                if not target.exists():
                    errors.append(f"{source}: expected rendered artifact missing: {target}")
                elif target.read_text(encoding="utf-8") != rendered:
                    errors.append(f"{source}: rendered artifact is stale: {target}")
            except Exception as exc:
                errors.append(f"{source}: {exc}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    action = "updated" if args.update else "validated"
    print(f"{action}: {len(sources)} fixture sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
