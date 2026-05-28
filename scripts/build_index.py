#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from cast_docs_core import (
    CONFIG_DIR,
    CastDocsError,
    discover_project_profile,
    href_kind,
    is_object,
    load_config,
    load_json,
    media_src_kind,
    output_path_from_policy,
    print_result,
    render_html,
    validate_document,
    validate_html_profile,
    validate_project_profile,
)


def validate_chapter(chapter: Any, section_path: str, root: Path, errors: list[str]) -> dict[str, Any] | None:
    if not is_object(chapter):
        errors.append(f"{section_path} chapter must be an object")
        return None
    for field in ("id", "title", "href", "source"):
        if not isinstance(chapter.get(field), str) or not chapter.get(field, "").strip():
            errors.append(f"{section_path}.{field} must be a non-empty string")
    href = chapter.get("href")
    if isinstance(href, str) and href_kind(href) != "relative":
        errors.append(f"{section_path}.href must be a relative path")
    source = chapter.get("source")
    if isinstance(source, str):
        source_path = (root / source).resolve()
        try:
            source_path.relative_to(root)
        except ValueError:
            errors.append(f"{section_path}.source must stay inside the input directory")
        if not source_path.is_file():
            errors.append(f"{section_path}.source not found: {source}")
    return chapter


def validate_manifest(manifest: Any, input_dir: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not is_object(manifest):
        return {}, ["document set manifest must be a JSON object"]

    for field in ("id", "title", "sections"):
        if field == "sections":
            if not isinstance(manifest.get(field), list) or not manifest.get(field):
                errors.append("sections must be a non-empty array")
        elif not isinstance(manifest.get(field), str) or not manifest.get(field, "").strip():
            errors.append(f"{field} must be a non-empty string")

    if manifest.get("language") is not None and manifest.get("language") not in {"zh-CN", "en"}:
        errors.append("language must be zh-CN or en")

    if is_object(manifest.get("logo")):
        src = manifest["logo"].get("src")
        if isinstance(src, str) and src and media_src_kind(src) not in {"data-image", "relative"}:
            errors.append("logo.src must be a data image or relative local image path")

    normalized_sections: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for section_index, section in enumerate(manifest.get("sections") or []):
        section_path = f"sections[{section_index}]"
        if not is_object(section):
            errors.append(f"{section_path} must be an object")
            continue
        section_id = section.get("id")
        label = section.get("label")
        chapters = section.get("chapters")
        if not isinstance(section_id, str) or not section_id.strip():
            errors.append(f"{section_path}.id must be a non-empty string")
        elif section_id in seen_ids:
            errors.append(f"{section_path}.id is duplicated: {section_id}")
        else:
            seen_ids.add(section_id)
        if not isinstance(label, str) or not label.strip():
            errors.append(f"{section_path}.label must be a non-empty string")
        if not isinstance(chapters, list) or not chapters:
            errors.append(f"{section_path}.chapters must be a non-empty array")
            chapters = []
        normalized_chapters = []
        for index, chapter in enumerate(chapters):
            validated = validate_chapter(chapter, f"{section_path}.chapters[{index}]", input_dir, errors)
            if validated is not None:
                normalized_chapters.append(validated)
        normalized_sections.append({"id": section_id, "label": label, "chapters": normalized_chapters})

    normalized = dict(manifest)
    normalized["sections"] = normalized_sections
    return normalized, errors


def index_doc_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    sections = []
    for section in manifest["sections"]:
        item_count = len(section["chapters"])
        sections.append(
            {
                "id": section["id"],
                "title": section["label"],
                "blocks": [
                    {
                        "type": "paragraph",
                        "text": f"{item_count} document{'' if item_count == 1 else 's'}",
                    },
                    {
                        "type": "chapter-list",
                        "items": [
                            {
                                "id": chapter.get("id"),
                                "number": chapter.get("number") or chapter.get("id"),
                                "title": chapter["title"],
                                "href": chapter["href"],
                            }
                            for chapter in section["chapters"]
                        ],
                    },
                ],
            }
        )

    title = manifest["title"]
    return {
        "metadata": {
            "title": title,
            "description": manifest.get("description", title),
            "language": manifest.get("language", "en"),
            "status": manifest.get("status", "draft"),
            "owner": manifest.get("owner", "unknown"),
            "updatedAt": manifest.get("updatedAt", ""),
            "showMeta": True,
            "logo": manifest.get("logo"),
            "shellLinks": manifest.get("shellLinks", []),
        },
        "manifest": {
            "documentType": manifest.get("documentType", "research-note"),
            "scenario": "none",
            "sections": [section["id"] for section in manifest["sections"]],
            "components": {
                "required": ["summary-block", "metadata-block", "toc", "section", "paragraph", "chapter-list"],
                "optional": ["shell-links"] if manifest.get("shellLinks") else [],
                "omitted": [],
            },
        },
        "sections": sections,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a CAST Docs document-set index from a manifest.")
    parser.add_argument("--manifest", type=Path, help="Document-set manifest JSON.")
    parser.add_argument("--input-dir", type=Path, help="Directory containing cast-docs-set.json.")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--profile-dir", type=Path)
    parser.add_argument(
        "--output-policy",
        choices=("explicit", "shareable", "local"),
        default="explicit",
    )
    args = parser.parse_args()

    manifest_path = args.manifest
    input_dir = args.input_dir
    if manifest_path is None:
        if input_dir is None:
            print("ERROR: provide --manifest or --input-dir", file=sys.stderr)
            return 1
        manifest_path = input_dir / "cast-docs-set.json"
    if input_dir is None:
        input_dir = manifest_path.parent
    input_dir = input_dir.resolve()

    try:
        profile = discover_project_profile(args.repo_root, args.profile_dir)
        if profile is not None:
            profile_result = validate_project_profile(profile, args.config_dir)
            if not profile_result.ok:
                print_result(profile_result)
                return 1

        manifest, errors = validate_manifest(load_json(manifest_path), input_dir)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1

        for section in manifest["sections"]:
            for chapter in section["chapters"]:
                chapter_doc = load_json((input_dir / chapter["source"]).resolve())
                chapter_result = validate_document(chapter_doc, args.config_dir)
                if not chapter_result.ok:
                    for error in chapter_result.errors:
                        print(f"ERROR: {chapter['source']}: {error}", file=sys.stderr)
                    return 1

        doc = index_doc_from_manifest(manifest)
        output = output_path_from_policy(args.output, doc, profile, args.output_policy)
        doc_result = validate_document(doc, args.config_dir)
        if not doc_result.ok:
            print_result(doc_result)
            return 1

        html_text = render_html(doc, layout_id="document-set", config_dir=args.config_dir, profile=profile)

        if args.validate:
            html_result = validate_html_profile(html_text, load_config("html-profile.json", args.config_dir))
            if not html_result.ok:
                print_result(html_result)
                return 1

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html_text, encoding="utf-8")
        print(f"rendered: {output}")
        return 0
    except CastDocsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
