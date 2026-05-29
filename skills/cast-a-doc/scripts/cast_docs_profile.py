from __future__ import annotations

import copy
import datetime as dt
import re
from pathlib import Path
from typing import Any

from cast_docs_common import (
    CONFIG_DIR,
    ROOT,
    SUPPORTED_LOCALES,
    CastDocsError,
    ProjectProfile,
    ValidationResult,
    is_object,
    load_config,
    load_json,
    load_optional_json,
    localized_value,
    merge_dicts,
    path_inside_root,
    resolve_inside_root,
    text,
)
from cast_docs_context import media_src_kind
from cast_docs_theme import validate_style_profile
from cast_docs_validation import validate_document, validate_logo


def discover_project_profile(
    repo_root: Path | None = None,
    profile_dir: Path | None = None,
) -> ProjectProfile | None:
    if repo_root is None and profile_dir is None:
        return None
    root = (repo_root or Path.cwd()).resolve()
    directory = (profile_dir or (root / ".cast-docs")).resolve()
    if not directory.exists():
        return None
    if not directory.is_dir():
        raise CastDocsError(f"profile path is not a directory: {directory}")
    try:
        directory.relative_to(root)
    except ValueError as exc:
        raise CastDocsError(f"profile directory must stay inside repo root: {directory}") from exc
    writing_style_path = directory / "writing-style.md"
    return ProjectProfile(
        repo_root=root,
        profile_dir=directory,
        project=load_optional_json(directory / "project.json"),
        preferences=load_optional_json(directory / "preferences.json"),
        i18n=load_optional_json(directory / "i18n.json"),
        glossary=load_optional_json(directory / "glossary.json"),
        writing_style=writing_style_path.read_text(encoding="utf-8") if writing_style_path.exists() else "",
        present=True,
    )


def validate_project_profile(profile: ProjectProfile, config_dir: Path = CONFIG_DIR) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    root = profile.repo_root

    if not profile.project:
        warnings.append("profile project.json is missing")
    elif profile.project.get("version") != 1:
        errors.append("project.json version must be 1")

    if profile.preferences and profile.preferences.get("version") != 1:
        errors.append("preferences.json version must be 1")
    if profile.i18n and profile.i18n.get("version") != 1:
        errors.append("i18n.json version must be 1")
    if profile.glossary and profile.glossary.get("version") != 1:
        errors.append("glossary.json version must be 1")

    document_types = {item["id"] for item in load_config("document-types.json", config_dir)["documentTypes"]}
    scenarios = {item["id"] for item in load_config("scenario-skeletons.json", config_dir)["scenarios"]}
    components = {item["id"] for item in load_config("components.json", config_dir)["components"]}

    default_locale = profile.project.get("defaultLocale")
    if default_locale is not None and default_locale not in SUPPORTED_LOCALES:
        errors.append("project.json defaultLocale must be zh-CN or en")
    display_owner = profile.project.get("displayOwner")
    if display_owner is not None and (not isinstance(display_owner, str) or not display_owner.strip()):
        errors.append("project.json displayOwner must be a non-empty string")
    default_type = profile.project.get("defaultDocumentType")
    if default_type is not None and default_type not in document_types:
        errors.append(f"project.json defaultDocumentType is unknown: {default_type}")
    default_scenario = profile.project.get("defaultScenario")
    if default_scenario is not None and default_scenario not in scenarios and default_scenario != "none":
        errors.append(f"project.json defaultScenario is unknown: {default_scenario}")

    output = profile.project.get("output")
    if output is not None:
        if not is_object(output):
            errors.append("project.json output must be an object")
        else:
            for key in ("defaultDir", "localDir"):
                if output.get(key) is not None:
                    path_inside_root(root, output[key], f"project.json output.{key}", errors)
            pattern = output.get("filenamePattern")
            if pattern is not None and (not isinstance(pattern, str) or "{slug}" not in pattern):
                errors.append("project.json output.filenamePattern must be a string containing {slug}")

    brand = profile.project.get("brand")
    if brand is not None:
        if not is_object(brand):
            errors.append("project.json brand must be an object")
        else:
            logo = brand.get("logo")
            if logo is not None:
                if not is_object(logo):
                    errors.append("project.json brand.logo must be an object")
                else:
                    src = logo.get("src")
                    metadata_errors: list[str] = []
                    validate_logo({"logo": logo}, metadata_errors)
                    errors.extend(f"project.json brand.logo: {error}" for error in metadata_errors)
                    if isinstance(src, str) and media_src_kind(src) == "relative":
                        asset = path_inside_root(root, src, "project.json brand.logo.src", errors)
                        if asset is not None and not asset.is_file():
                            errors.append(f"project.json brand.logo.src not found: {src}")

    validate_style_profile(profile.project.get("styleProfile"), config_dir, errors)

    locales = profile.i18n.get("locales") if profile.i18n else None
    if locales is not None:
        if not isinstance(locales, list) or not locales:
            errors.append("i18n.json locales must be a non-empty array")
        else:
            unsupported = [locale for locale in locales if locale not in SUPPORTED_LOCALES]
            if unsupported:
                errors.append(f"i18n.json locales contains unsupported locales: {', '.join(map(str, unsupported))}")
            if default_locale is not None and default_locale not in locales:
                errors.append("project.json defaultLocale must be present in i18n.json locales")
            i18n_default = profile.i18n.get("defaultLocale")
            if i18n_default is not None and i18n_default not in locales:
                errors.append("i18n.json defaultLocale must be present in i18n.json locales")
            fallback = profile.i18n.get("fallbackLocale")
            if fallback is not None and fallback not in locales:
                errors.append("i18n.json fallbackLocale must be present in i18n.json locales")

    scenario_defaults = profile.preferences.get("scenarioDefaults") if profile.preferences else None
    if scenario_defaults is not None:
        if not is_object(scenario_defaults):
            errors.append("preferences.json scenarioDefaults must be an object")
        else:
            for scenario_id, defaults in scenario_defaults.items():
                if scenario_id not in scenarios and scenario_id != "none":
                    errors.append(f"preferences.json scenarioDefaults contains unknown scenario: {scenario_id}")
                    continue
                if not is_object(defaults):
                    errors.append(f"preferences.json scenarioDefaults.{scenario_id} must be an object")
                    continue
                document_type = defaults.get("documentType")
                if document_type is not None and document_type not in document_types:
                    errors.append(f"preferences.json scenarioDefaults.{scenario_id}.documentType is unknown: {document_type}")
                template = defaults.get("template")
                if template is not None:
                    template_path = path_inside_root(root, template, f"preferences.json scenarioDefaults.{scenario_id}.template", errors)
                    if template_path is not None:
                        if not template_path.is_file():
                            errors.append(f"preferences.json scenarioDefaults.{scenario_id}.template not found: {template}")
                        else:
                            try:
                                template_doc = load_json(template_path)
                                result = validate_document(template_doc, config_dir)
                                errors.extend(f"{template}: {error}" for error in result.errors)
                            except CastDocsError as exc:
                                errors.append(str(exc))
                for component_key in ("preferredComponents", "omitWhenEmpty"):
                    values = defaults.get(component_key)
                    if values is not None:
                        if not isinstance(values, list):
                            errors.append(f"preferences.json scenarioDefaults.{scenario_id}.{component_key} must be an array")
                        else:
                            for component_id in values:
                                if component_id not in components:
                                    errors.append(
                                        f"preferences.json scenarioDefaults.{scenario_id}.{component_key} contains unknown component: {component_id}"
                                    )

    return ValidationResult(errors, warnings)


def profile_default_metadata(profile: ProjectProfile | None) -> dict[str, Any]:
    if profile is None:
        return {}
    metadata: dict[str, Any] = {}
    project = profile.project
    if isinstance(project.get("defaultLocale"), str):
        metadata["language"] = project["defaultLocale"]
    if isinstance(project.get("owner"), str):
        metadata["owner"] = project["owner"]
    brand = project.get("brand")
    if is_object(brand) and is_object(brand.get("logo")):
        metadata["logo"] = brand["logo"]
    return metadata


def project_display_name(profile: ProjectProfile | None) -> str:
    if profile is None:
        return ""
    project = profile.project
    for key in ("displayName", "name"):
        value = project.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def project_owner_display_name(metadata: dict[str, Any], profile: ProjectProfile | None) -> str:
    if profile is not None:
        display_owner = profile.project.get("displayOwner")
        if isinstance(display_owner, str) and display_owner.strip():
            return display_owner.strip()
    owner = metadata.get("owner")
    if isinstance(owner, str) and owner.strip():
        return owner.strip()
    return ""


def apply_project_profile(doc: dict[str, Any], profile: ProjectProfile | None) -> dict[str, Any]:
    if profile is None:
        return doc
    merged = copy.deepcopy(doc)
    metadata = merged.get("metadata")
    if not is_object(metadata):
        metadata = {}
    merged["metadata"] = merge_dicts(profile_default_metadata(profile), metadata)

    manifest = merged.get("manifest")
    if is_object(manifest):
        scenario = manifest.get("scenario") or profile.project.get("defaultScenario")
        defaults = {}
        scenario_defaults = profile.preferences.get("scenarioDefaults")
        if isinstance(scenario, str) and is_object(scenario_defaults):
            scenario_entry = scenario_defaults.get(scenario)
            if is_object(scenario_entry):
                defaults = scenario_entry
        if not manifest.get("documentType"):
            document_type = defaults.get("documentType") or profile.project.get("defaultDocumentType")
            if isinstance(document_type, str):
                manifest["documentType"] = document_type
        if not manifest.get("scenario") and isinstance(profile.project.get("defaultScenario"), str):
            manifest["scenario"] = profile.project["defaultScenario"]
    return merged


def slugify_filename(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "document"


def output_path_from_policy(
    explicit_output: Path | None,
    doc: dict[str, Any],
    profile: ProjectProfile | None,
    policy: str,
) -> Path:
    if explicit_output is not None:
        return explicit_output
    if profile is None:
        raise CastDocsError("--output is required when no project profile is loaded")
    if policy == "explicit":
        raise CastDocsError("--output is required when --output-policy explicit is used")

    output = profile.project.get("output")
    if not is_object(output):
        output = {}
    directory_key = "localDir" if policy == "local" else "defaultDir"
    fallback_dir = ".cast-docs/out" if policy == "local" else "docs/cast-docs"
    directory = text(output.get(directory_key) or fallback_dir)
    output_dir = resolve_inside_root(profile.repo_root, directory, f"project.json output.{directory_key}")

    title = localized_value(doc.get("metadata", {}).get("title", ""), doc.get("metadata", {}).get("language", "en"), "en")
    pattern = text(output.get("filenamePattern") or "{date}-{slug}.html")
    slug = slugify_filename(text(title))
    filename = pattern.replace("{date}", dt.date.today().isoformat()).replace("{slug}", slug)
    if "/" in filename or "\\" in filename or not filename.endswith(".html"):
        raise CastDocsError("project.json output.filenamePattern must produce an .html filename")
    return output_dir / filename
