#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

from cast_docs_core import (
    CONFIG_DIR,
    CastDocsError,
    apply_project_profile,
    discover_project_profile,
    is_object,
    load_config,
    load_json,
    merge_dicts,
    print_result,
    resolve_inside_root,
    validate_document,
    validate_project_profile,
)


def template_from_profile(profile: object, scenario: str | None) -> Path | None:
    if profile is None or not scenario:
        return None
    preferences = getattr(profile, "preferences", {})
    scenario_defaults = preferences.get("scenarioDefaults") if is_object(preferences) else None
    defaults = scenario_defaults.get(scenario) if is_object(scenario_defaults) else None
    if not is_object(defaults) or not isinstance(defaults.get("template"), str):
        return None
    return resolve_inside_root(profile.repo_root, defaults["template"], f"preferences.json scenarioDefaults.{scenario}.template")


def infer_scenario(doc: dict[str, object], profile: object | None) -> str | None:
    manifest = doc.get("manifest")
    if is_object(manifest) and isinstance(manifest.get("scenario"), str):
        return manifest["scenario"]
    if profile is not None and isinstance(profile.project.get("defaultScenario"), str):
        return profile.project["defaultScenario"]
    return None


def merge_template(template_doc: dict[str, object], input_doc: dict[str, object]) -> dict[str, object]:
    merged = merge_dicts(template_doc, input_doc)
    if is_object(template_doc.get("manifest")) and is_object(input_doc.get("manifest")):
        template_components = template_doc["manifest"].get("components")
        input_components = input_doc["manifest"].get("components")
        if is_object(template_components) and is_object(input_components):
            components = copy.deepcopy(template_components)
            for group in ("required", "optional", "omitted"):
                base = components.get(group, [])
                override = input_components.get(group, [])
                if isinstance(base, list) and isinstance(override, list):
                    components[group] = [*base, *[item for item in override if item not in base]]
            merged["manifest"]["components"] = components
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a CAST Docs project template to document JSON.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--template", type=Path)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--profile-dir", type=Path)
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    try:
        profile = discover_project_profile(args.repo_root, args.profile_dir)
        if profile is not None:
            profile_result = validate_project_profile(profile, args.config_dir)
            if not profile_result.ok:
                print_result(profile_result)
                return 1

        input_doc = load_json(args.input)
        if not is_object(input_doc):
            raise CastDocsError("input document must be a JSON object")

        scenario = infer_scenario(input_doc, profile)
        template_path = args.template or template_from_profile(profile, scenario)
        if template_path is not None:
            template_doc = load_json(template_path)
            if not is_object(template_doc):
                raise CastDocsError("template document must be a JSON object")
            output_doc = merge_template(template_doc, input_doc)
        else:
            output_doc = input_doc

        output_doc = apply_project_profile(output_doc, profile)

        if args.validate:
            result = validate_document(output_doc, args.config_dir)
            if not result.ok:
                print_result(result)
                return 1

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote: {args.output}")
        return 0
    except CastDocsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
