#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import hashlib
import html
import json
import mimetypes
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
TEMPLATE_DIR = ROOT / "assets" / "template-modules"

SECTION_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SAFE_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RAW_SVG_RISK_RE = re.compile(r"<\s*(script|iframe|object|embed)\b|on[a-z]+\s*=", re.IGNORECASE)
UNRESOLVED_RE = re.compile(r"\{\{\s*[A-Z_]+\s*\}\}")
DATA_IMAGE_RE = re.compile(r"^data:image/(?:png|jpe?g|gif|webp);base64,[A-Za-z0-9+/=\s]+$", re.IGNORECASE)
SUPPORTED_LOCALES = ("en", "zh-CN")
SUPPORTED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


class CastDocsError(Exception):
    pass


@dataclass
class ValidationResult:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class RenderContext:
    active_locale: str
    locales: list[str]
    i18n: dict[str, Any]
    config_dir: Path
    repo_root: Path = ROOT
    metadata: dict[str, Any] | None = None
    code_index: int = 0


@dataclass
class ProjectProfile:
    repo_root: Path
    profile_dir: Path
    project: dict[str, Any]
    preferences: dict[str, Any]
    i18n: dict[str, Any]
    glossary: dict[str, Any]
    writing_style: str
    present: bool = False


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CastDocsError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def load_config(name: str, config_dir: Path = CONFIG_DIR) -> Any:
    return load_json(config_dir / name)


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = load_json(path)
    if not is_object(value):
        raise CastDocsError(f"{path}: expected a JSON object")
    return value


def load_template_module(name: str, template_dir: Path = TEMPLATE_DIR) -> str:
    path = template_dir / name
    if not path.exists():
        raise CastDocsError(f"template module not found: {path}")
    return path.read_text(encoding="utf-8")


def resolve_inside_root(root: Path, relative_path: str, label: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise CastDocsError(f"{label} must be a non-empty repository-relative path")
    path = Path(relative_path)
    if path.is_absolute():
        raise CastDocsError(f"{label} must be repository-relative: {relative_path}")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise CastDocsError(f"{label} must stay inside the repository: {relative_path}") from exc
    return resolved


def path_inside_root(root: Path, relative_path: str, label: str, errors: list[str]) -> Path | None:
    try:
        return resolve_inside_root(root, relative_path, label)
    except CastDocsError as exc:
        errors.append(str(exc))
        return None


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def is_object(value: Any) -> bool:
    return isinstance(value, dict)


def text(value: Any) -> str:
    return "" if value is None else str(value)


def esc(value: Any) -> str:
    return html.escape(text(value), quote=True)


def attr(value: Any) -> str:
    return html.escape(text(value), quote=True)


def slug_to_title(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("-"))


def is_localized_object(value: Any) -> bool:
    return is_object(value) and any(locale in value for locale in SUPPORTED_LOCALES)


def locale_is_supported(locale: Any) -> bool:
    return isinstance(locale, str) and locale in SUPPORTED_LOCALES


def normalize_locale(locale: Any, fallback: str = "en") -> str:
    return locale if locale_is_supported(locale) else fallback


def localized_value(value: Any, locale: str, fallback: str = "en") -> Any:
    if not is_localized_object(value):
        return value
    if locale in value:
        return value[locale]
    if fallback in value:
        return value[fallback]
    for supported_locale in SUPPORTED_LOCALES:
        if supported_locale in value:
            return value[supported_locale]
    return ""


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if is_object(value) and is_object(merged.get(key)):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def collect_locales_from_value(value: Any, found: set[str]) -> None:
    if is_localized_object(value):
        for locale in SUPPORTED_LOCALES:
            if locale in value:
                found.add(locale)
                collect_locales_from_value(value[locale], found)
        return
    if isinstance(value, list):
        for item in value:
            collect_locales_from_value(item, found)
    elif is_object(value):
        for item in value.values():
            collect_locales_from_value(item, found)


def document_locales(doc: dict[str, Any]) -> list[str]:
    metadata = doc.get("metadata", {}) if is_object(doc.get("metadata")) else {}
    default_locale = normalize_locale(metadata.get("language"), "en")
    configured = metadata.get("locales")
    if isinstance(configured, list):
        locales = [locale for locale in configured if locale_is_supported(locale)]
    else:
        found: set[str] = set()
        collect_locales_from_value(doc, found)
        locales = [locale for locale in SUPPORTED_LOCALES if locale in found]
    if default_locale not in locales:
        locales.insert(0, default_locale)
    return locales or [default_locale]


def default_locale_for_context(ctx: RenderContext | None) -> str:
    return ctx.active_locale if ctx else "en"


def i18n_label(i18n: dict[str, Any], locale: str, key: str, fallback: str = "") -> str:
    default_locale = i18n.get("defaultLocale", "en")
    locales = i18n.get("locales", {}) if is_object(i18n.get("locales")) else {}
    for candidate in (locale, default_locale, "en"):
        bundle = locales.get(candidate)
        strings = bundle.get("strings", {}) if is_object(bundle) else {}
        value = strings.get(key) if is_object(strings) else None
        if isinstance(value, str):
            return value
    return fallback


def locale_display_label(i18n: dict[str, Any], locale: str) -> str:
    locales = i18n.get("locales", {}) if is_object(i18n.get("locales")) else {}
    bundle = locales.get(locale)
    if is_object(bundle) and isinstance(bundle.get("label"), str):
        return bundle["label"]
    return locale


def tr(ctx: RenderContext | None, key: str, fallback: str) -> str:
    if ctx is None:
        return fallback
    return i18n_label(ctx.i18n, ctx.active_locale, key, fallback)


def render_i18n_text(ctx: RenderContext | None, key: str, fallback: str) -> str:
    value = esc(tr(ctx, key, fallback))
    if ctx is None or len(ctx.locales) <= 1:
        return value
    return f"<span data-i18n-key=\"{attr(key)}\">{value}</span>"


def href_kind(href: str) -> str | None:
    if href.startswith("#"):
        return "anchor"
    if href.startswith(("./", "../", "/")):
        return "relative"
    parsed = urlparse(href)
    if parsed.scheme in ("http", "https"):
        return parsed.scheme
    if parsed.scheme == "openinfinder":
        return "openinfinder"
    if not parsed.scheme and not href.startswith("//"):
        return "relative"
    return None


def media_src_kind(src: str) -> str | None:
    if DATA_IMAGE_RE.match(src.strip()):
        return "data-image"
    return href_kind(src)


def validate_shell_links(metadata: dict[str, Any], errors: list[str]) -> None:
    links = metadata.get("shellLinks", [])
    if links is None:
        return
    if not isinstance(links, list):
        errors.append("metadata.shellLinks must be an array")
        return
    if len(links) > 3:
        errors.append("metadata.shellLinks must contain at most 3 items")
    for index, link in enumerate(links):
        path = f"metadata.shellLinks[{index}]"
        if not is_object(link):
            errors.append(f"{path} must be an object")
            continue
        label = link.get("label")
        href = link.get("href")
        placement = link.get("placement", "topbar")
        validate_localized_string(label, f"{path}.label", errors, non_empty=True)
        if not isinstance(href, str) or not href.strip():
            errors.append(f"{path}.href must be a non-empty string")
        elif href_kind(href) not in {"anchor", "relative", "http", "https"}:
            errors.append(f"{path}.href uses an unsupported URL scheme")
        if placement not in {"topbar", "footer"}:
            errors.append(f"{path}.placement must be topbar or footer")


def validate_logo(metadata: dict[str, Any], errors: list[str]) -> None:
    logo = metadata.get("logo")
    if logo is None:
        return
    if not is_object(logo):
        errors.append("metadata.logo must be an object")
        return
    src = logo.get("src")
    if not isinstance(src, str) or not src.strip():
        errors.append("metadata.logo.src must be a non-empty string")
    elif media_src_kind(src) not in {"data-image", "relative"}:
        errors.append("metadata.logo.src must be a data image or relative local image path")
    validate_localized_string(logo.get("alt"), "metadata.logo.alt", errors, non_empty=True)
    href = logo.get("href")
    if href is not None:
        if not isinstance(href, str) or not href.strip():
            errors.append("metadata.logo.href must be a non-empty string")
        elif href_kind(href) not in {"anchor", "relative", "http", "https"}:
            errors.append("metadata.logo.href uses an unsupported URL scheme")


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


def collect_block_types(blocks: list[Any], found: set[str]) -> None:
    for block in blocks:
        if not is_object(block):
            continue
        block_type = block.get("type")
        if isinstance(block_type, str):
            found.add(block_type)
        collect_block_types(as_list(block.get("blocks")), found)
        for column in as_list(block.get("columns")):
            if is_object(column):
                collect_block_types(as_list(column.get("blocks")), found)
        for view in as_list(block.get("views")):
            if is_object(view):
                collect_block_types(as_list(view.get("blocks")), found)


INLINE_MARK_CATEGORIES: dict[str, str] = {
    "strong": "visual",
    "em": "visual",
    "code": "visual",
    "del": "visual",
    "u": "visual",
    "mark": "visual",
    "deprecated": "semantic",
    "term": "semantic",
    "metric": "semantic",
    "link": "ref",
    "ref": "ref",
}
INLINE_LINK_SCHEMES = {"anchor", "relative", "http", "https"}
CHAPTER_ICON_PATHS = {
    "overview": '<path d="M4 7h16"></path><path d="M4 12h10"></path><path d="M4 17h13"></path>',
    "features": '<path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.2 6.4 20.2 7.5 14 3 9.6l6.2-.9L12 3z"></path>',
    "interaction": '<path d="M5 6h14v9H8l-3 3V6z"></path><path d="M9 10h6"></path>',
    "stack": '<path d="M12 3l8 4-8 4-8-4 8-4z"></path><path d="M4 12l8 4 8-4"></path><path d="M4 17l8 4 8-4"></path>',
    "quality": '<path d="M12 3l7 4v5c0 4.5-3 7.6-7 9-4-1.4-7-4.5-7-9V7l7-4z"></path><path d="M9 12l2 2 4-4"></path>',
    "architecture": '<rect x="4" y="4" width="6" height="6" rx="1"></rect><rect x="14" y="4" width="6" height="6" rx="1"></rect><rect x="9" y="14" width="6" height="6" rx="1"></rect><path d="M10 7h4"></path><path d="M12 10v4"></path>',
    "gate": '<path d="M5 20V9a7 7 0 0 1 14 0v11"></path><path d="M3 20h18"></path><path d="M9 14h6"></path>',
    "model": '<path d="M6 4h9l3 3v13H6z"></path><path d="M14 4v4h4"></path><path d="M9 12h6"></path><path d="M9 16h4"></path>',
    "release": '<path d="M12 3v12"></path><path d="M8 7l4-4 4 4"></path><path d="M5 15v4h14v-4"></path>',
    "verification": '<path d="M20 6L9 17l-5-5"></path>',
    "decisions": '<path d="M12 3v13"></path><circle cx="12" cy="20" r="1"></circle>',
}


def inline_anchor(href: Any, inner: str) -> str | None:
    if not isinstance(href, str):
        return None
    kind = href_kind(href)
    if kind not in INLINE_LINK_SCHEMES:
        return None
    target = " target=\"_blank\" rel=\"noopener noreferrer\"" if kind in ("http", "https") else ""
    return f"<a href=\"{attr(href)}\"{target}>{inner}</a>"


def apply_inline_mark(mark: Any, inner: str) -> str:
    if isinstance(mark, str):
        mark_type, spec = mark, {}
    elif is_object(mark) and isinstance(mark.get("type"), str):
        mark_type, spec = mark["type"], mark
    else:
        return inner
    category = INLINE_MARK_CATEGORIES.get(mark_type)
    if category == "visual":
        return f"<{mark_type}>{inner}</{mark_type}>"
    if category == "semantic":
        if mark_type == "term":
            definition = spec.get("definition")
            title = f" title=\"{attr(definition)}\"" if isinstance(definition, str) and definition else ""
            return f"<span data-mark=\"term\"{title}>{inner}</span>"
        return f"<span data-mark=\"{attr(mark_type)}\">{inner}</span>"
    if category == "ref":
        if mark_type == "link":
            return inline_anchor(spec.get("href"), inner) or inner
        coded = f"<code data-mark=\"ref\">{inner}</code>"
        return inline_anchor(spec.get("url"), coded) or coded
    return inner


def render_run(run: Any) -> str:
    if not is_object(run):
        return ""
    out = esc(run.get("text"))
    for mark in as_list(run.get("marks")):
        out = apply_inline_mark(mark, out)
    return out


def render_chapter_icon(icon: Any) -> str:
    if not isinstance(icon, str) or not icon.strip():
        return ""
    icon_name = icon.strip()
    path = CHAPTER_ICON_PATHS.get(icon_name)
    if path:
        inner = (
            '<svg class="chapter-icon-svg" viewBox="0 0 24 24" width="18" height="18" '
            'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            f"{path}</svg>"
        )
    else:
        inner = esc(icon_name[:2])
    return f"<span class=\"chapter-icon\" aria-hidden=\"true\">{inner}</span>"


def render_inline_plain_text(value: Any) -> str:
    raw = text(value)
    if "`" not in raw:
        return esc(raw)
    parts = raw.split("`")
    out: list[str] = []
    index = 0
    while index < len(parts):
        out.append(esc(parts[index]))
        if index + 1 >= len(parts):
            break
        code_part = parts[index + 1]
        if index + 2 >= len(parts):
            out.append("`")
            out.append(esc(code_part))
            break
        if code_part:
            out.append(f"<code>{esc(code_part)}</code>")
        else:
            out.append("``")
        index += 2
    return "".join(out)


def render_inline_for_locale(value: Any, locale: str, fallback: str = "en") -> str:
    selected = localized_value(value, locale, fallback)
    if isinstance(selected, list):
        return "".join(render_run(run) for run in selected)
    return render_inline_plain_text(selected)


def render_localized_spans(value: Any, renderer: Any, ctx: RenderContext | None) -> str:
    if not is_localized_object(value) or ctx is None or len(ctx.locales) <= 1:
        return renderer(localized_value(value, default_locale_for_context(ctx)))
    out: list[str] = []
    for locale in ctx.locales:
        active = "true" if locale == ctx.active_locale else "false"
        out.append(
            f"<span data-locale=\"{attr(locale)}\" data-locale-active=\"{active}\">"
            f"{renderer(localized_value(value, locale, ctx.active_locale))}"
            "</span>"
        )
    return "".join(out)


def render_text(value: Any, ctx: RenderContext | None = None) -> str:
    return render_localized_spans(value, esc, ctx)


def render_inline(value: Any, ctx: RenderContext | None = None) -> str:
    if is_localized_object(value) and ctx is not None and len(ctx.locales) > 1:
        return render_localized_spans(
            value,
            lambda selected: render_inline_for_locale(selected, default_locale_for_context(ctx), default_locale_for_context(ctx)),
            ctx,
        )
    if isinstance(value, list):
        return "".join(render_run(run) for run in value)
    return render_inline_plain_text(localized_value(value, default_locale_for_context(ctx)))


def svg_text_for_locale(value: Any, locale: str, fallback: str = "en") -> str:
    return html.escape(text(localized_value(value, locale, fallback)), quote=False)


def render_svg_text_variants(
    value: Any,
    ctx: RenderContext | None,
    attrs: str,
    *,
    anchor: str | None = None,
) -> str:
    if is_localized_object(value) and ctx is not None and len(ctx.locales) > 1:
        nodes = []
        for locale in ctx.locales:
            active = "true" if locale == ctx.active_locale else "false"
            nodes.append(
                f"<text {attrs} data-locale=\"{attr(locale)}\" data-locale-active=\"{active}\""
                f"{anchor or ''}>{svg_text_for_locale(value, locale, ctx.active_locale)}</text>"
            )
        return "".join(nodes)
    return f"<text {attrs}{anchor or ''}>{svg_text_for_locale(value, default_locale_for_context(ctx))}</text>"


def validate_inline_mark(mark: Any, path: str, errors: list[str]) -> None:
    if isinstance(mark, str):
        category = INLINE_MARK_CATEGORIES.get(mark)
        if category is None:
            errors.append(f"{path} is an unknown inline mark: {mark}")
        elif category == "ref":
            errors.append(f"{path} '{mark}' must use object form with its required fields")
        return
    if not is_object(mark) or not isinstance(mark.get("type"), str):
        errors.append(f"{path} must be a mark name or an object with a string type")
        return
    mark_type = mark["type"]
    category = INLINE_MARK_CATEGORIES.get(mark_type)
    if category is None:
        errors.append(f"{path}.type is an unknown inline mark: {mark_type}")
        return
    if mark_type == "link":
        href = mark.get("href")
        if not isinstance(href, str) or href_kind(href) not in INLINE_LINK_SCHEMES:
            errors.append(f"{path}.href must be an anchor, relative, or http(s) URL")
    elif mark_type == "ref":
        if not isinstance(mark.get("path"), str) or not mark.get("path"):
            errors.append(f"{path}.path must be a non-empty string")
        line = mark.get("line")
        if line is not None and (not isinstance(line, int) or isinstance(line, bool)):
            errors.append(f"{path}.line must be an integer")
        url = mark.get("url")
        if url is not None and (not isinstance(url, str) or href_kind(url) not in INLINE_LINK_SCHEMES):
            errors.append(f"{path}.url must be an anchor, relative, or http(s) URL")


def validate_inline(value: Any, path: str, errors: list[str]) -> None:
    if is_localized_object(value):
        for locale in SUPPORTED_LOCALES:
            if locale in value:
                validate_inline(value[locale], f"{path}.{locale}", errors)
        return
    if isinstance(value, str):
        return
    if not isinstance(value, list):
        errors.append(f"{path} must be a string or an array of runs")
        return
    for index, run in enumerate(value):
        run_path = f"{path}[{index}]"
        if not is_object(run):
            errors.append(f"{run_path} must be a run object")
            continue
        if not isinstance(run.get("text"), str):
            errors.append(f"{run_path}.text must be a string")
        for mark_index, mark in enumerate(as_list(run.get("marks"))):
            validate_inline_mark(mark, f"{run_path}.marks[{mark_index}]", errors)


def validate_localized_string(value: Any, path: str, errors: list[str], *, non_empty: bool = False) -> None:
    if isinstance(value, str):
        if non_empty and not value:
            errors.append(f"{path} must be a non-empty string")
        return
    if is_localized_object(value):
        for locale in SUPPORTED_LOCALES:
            if locale in value:
                localized = value[locale]
                if not isinstance(localized, str):
                    errors.append(f"{path}.{locale} must be a string")
                elif non_empty and not localized:
                    errors.append(f"{path}.{locale} must be a non-empty string")
        return
    errors.append(f"{path} must be a string or localized string object")


def validate_block(block: Any, path: str, errors: list[str]) -> None:
    if not is_object(block):
        errors.append(f"{path} must be an object")
        return
    block_type = block.get("type")
    if not isinstance(block_type, str):
        errors.append(f"{path}.type must be a string")
        return

    def require_string(key: str) -> None:
        validate_localized_string(block.get(key), f"{path}.{key}", errors, non_empty=True)

    def require_array(key: str) -> list[Any]:
        value = block.get(key)
        if not isinstance(value, list):
            errors.append(f"{path}.{key} must be an array")
            return []
        return value

    if block_type == "summary":
        for index, item in enumerate(require_array("items")):
            if not is_object(item):
                errors.append(f"{path}.items[{index}] must be an object")
                continue
            validate_localized_string(item.get("label"), f"{path}.items[{index}].label", errors, non_empty=True)
            validate_inline(item.get("body"), f"{path}.items[{index}].body", errors)
    elif block_type == "paragraph":
        validate_inline(block.get("text"), f"{path}.text", errors)
    elif block_type == "list":
        for index, item in enumerate(require_array("items")):
            validate_inline(item, f"{path}.items[{index}]", errors)
    elif block_type == "callout":
        if block.get("variant") not in {"info", "warning", "danger", "success"}:
            errors.append(f"{path}.variant must be one of info, warning, danger, success")
        validate_inline(block.get("body"), f"{path}.body", errors)
    elif block_type == "table":
        headers = require_array("headers")
        rows = require_array("rows")
        for index, header in enumerate(headers):
            validate_localized_string(header, f"{path}.headers[{index}]", errors)
        for row_index, row in enumerate(rows):
            if not isinstance(row, list):
                errors.append(f"{path}.rows[{row_index}] must be an array")
                continue
            if headers and len(row) != len(headers):
                errors.append(f"{path}.rows[{row_index}] must have {len(headers)} cells")
            for cell_index, cell in enumerate(row):
                validate_inline(cell, f"{path}.rows[{row_index}][{cell_index}]", errors)
    elif block_type == "details":
        require_string("summary")
        for index, child in enumerate(require_array("blocks")):
            validate_block(child, f"{path}.blocks[{index}]", errors)
    elif block_type == "code":
        if not isinstance(block.get("code"), str):
            errors.append(f"{path}.code must be a string")
    elif block_type == "diagram":
        require_string("kind")
        source = block.get("source")
        if not is_object(source):
            errors.append(f"{path}.source must be an object")
        else:
            fmt = source.get("format")
            if fmt == "structured-sequence":
                for index, step in enumerate(as_list(source.get("steps"))):
                    if not is_object(step):
                        errors.append(f"{path}.source.steps[{index}] must be an object")
                        continue
                    for key in ("from", "to", "label"):
                        validate_localized_string(step.get(key), f"{path}.source.steps[{index}].{key}", errors, non_empty=True)
            elif fmt == "structured-flow":
                for index, node in enumerate(as_list(source.get("nodes"))):
                    if not is_object(node) or not isinstance(node.get("id"), str):
                        errors.append(f"{path}.source.nodes[{index}] must include string id and label")
                        continue
                    validate_localized_string(node.get("label"), f"{path}.source.nodes[{index}].label", errors)
                for index, edge in enumerate(as_list(source.get("edges"))):
                    if not is_object(edge) or not isinstance(edge.get("from"), str) or not isinstance(edge.get("to"), str):
                        errors.append(f"{path}.source.edges[{index}] must include string from and to")
            elif fmt == "structured-er":
                for index, entity in enumerate(as_list(source.get("entities"))):
                    if not is_object(entity) or not isinstance(entity.get("id"), str):
                        errors.append(f"{path}.source.entities[{index}] must include string id and name")
                        continue
                    validate_localized_string(entity.get("name"), f"{path}.source.entities[{index}].name", errors, non_empty=True)
                    for field_index, field in enumerate(as_list(entity.get("fields"))):
                        validate_localized_string(field, f"{path}.source.entities[{index}].fields[{field_index}]", errors, non_empty=True)
                for index, relationship in enumerate(as_list(source.get("relationships"))):
                    if (
                        not is_object(relationship)
                        or not isinstance(relationship.get("from"), str)
                        or not isinstance(relationship.get("to"), str)
                    ):
                        errors.append(f"{path}.source.relationships[{index}] must include string from and to")
                        continue
                    if relationship.get("label") is not None:
                        validate_localized_string(relationship.get("label"), f"{path}.source.relationships[{index}].label", errors)
            elif fmt == "svg":
                content = source.get("content")
                if not isinstance(content, str) or not content.strip():
                    errors.append(f"{path}.source.content must be a non-empty SVG string")
                elif RAW_SVG_RISK_RE.search(content):
                    errors.append(f"{path}.source.content contains forbidden SVG content")
            else:
                errors.append(f"{path}.source.format is unsupported")
        download_name = block.get("downloadName")
        if download_name is not None and (not isinstance(download_name, str) or not SAFE_NAME_RE.match(download_name)):
            errors.append(f"{path}.downloadName must be a safe kebab-case name")
        if block.get("title") is not None:
            validate_localized_string(block.get("title"), f"{path}.title", errors)
    elif block_type == "diff":
        if block.get("title") is not None:
            validate_localized_string(block.get("title"), f"{path}.title", errors)
        for side_key in ("left", "right"):
            side = block.get(side_key)
            if not is_object(side):
                errors.append(f"{path}.{side_key} must be an object")
                continue
            validate_localized_string(side.get("label"), f"{path}.{side_key}.label", errors, non_empty=True)
            for index, line in enumerate(as_list(side.get("lines"))):
                if not is_object(line):
                    errors.append(f"{path}.{side_key}.lines[{index}] must be an object")
                    continue
                if line.get("kind") not in {"add", "remove", "warning", "context"}:
                    errors.append(f"{path}.{side_key}.lines[{index}].kind is unsupported")
                validate_localized_string(line.get("text"), f"{path}.{side_key}.lines[{index}].text", errors)
                if line.get("highlight") is not None and not isinstance(line.get("highlight"), bool):
                    errors.append(f"{path}.{side_key}.lines[{index}].highlight must be boolean")
    elif block_type == "participants":
        for index, item in enumerate(require_array("items")):
            if not is_object(item):
                errors.append(f"{path}.items[{index}] must include a string name")
                continue
            validate_localized_string(item.get("name"), f"{path}.items[{index}].name", errors, non_empty=True)
            if item.get("role") is not None:
                validate_localized_string(item.get("role"), f"{path}.items[{index}].role", errors)
            validate_inline(item.get("responsibility"), f"{path}.items[{index}].responsibility", errors)
    elif block_type == "source-refs":
        for index, item in enumerate(require_array("items")):
            if not is_object(item) or not isinstance(item.get("url"), str):
                errors.append(f"{path}.items[{index}] must include label and url")
                continue
            validate_localized_string(item.get("label"), f"{path}.items[{index}].label", errors, non_empty=True)
            if item.get("text") is not None:
                validate_localized_string(item.get("text"), f"{path}.items[{index}].text", errors)
            if href_kind(item["url"]) not in {"anchor", "relative", "http", "https"}:
                errors.append(f"{path}.items[{index}].url uses an unsupported URL scheme")
    elif block_type == "files":
        for index, item in enumerate(require_array("items")):
            if not is_object(item) or not isinstance(item.get("path"), str):
                errors.append(f"{path}.items[{index}] must include path")
                continue
            if item.get("note") is not None:
                validate_localized_string(item.get("note"), f"{path}.items[{index}].note", errors)
    elif block_type == "action":
        require_string("title")
        validate_inline(block.get("description"), f"{path}.description", errors)
        if block.get("prompt") is not None:
            validate_localized_string(block.get("prompt"), f"{path}.prompt", errors)
        if block.get("priority", "none") not in {"p0", "p1", "p2", "none"}:
            errors.append(f"{path}.priority is unsupported")
    elif block_type == "values-grid":
        for index, item in enumerate(require_array("items")):
            if not is_object(item):
                errors.append(f"{path}.items[{index}] must include a string title")
                continue
            validate_localized_string(item.get("title"), f"{path}.items[{index}].title", errors, non_empty=True)
            validate_inline(item.get("body"), f"{path}.items[{index}].body", errors)
    elif block_type == "acceptance-criteria":
        for index, item in enumerate(require_array("items")):
            validate_inline(item, f"{path}.items[{index}]", errors)
    elif block_type == "open-questions":
        if block.get("title") is not None:
            validate_localized_string(block.get("title"), f"{path}.title", errors, non_empty=True)
        for index, item in enumerate(require_array("questions")):
            validate_inline(item, f"{path}.questions[{index}]", errors)
    elif block_type == "media":
        for index, item in enumerate(require_array("items")):
            if not is_object(item):
                errors.append(f"{path}.items[{index}] must be an object")
                continue
            src = item.get("src")
            if not isinstance(src, str) or not src.strip():
                errors.append(f"{path}.items[{index}].src must be a non-empty string")
            elif media_src_kind(src) not in {"data-image", "relative", "http", "https"}:
                errors.append(f"{path}.items[{index}].src uses an unsupported image source")
            validate_localized_string(item.get("alt"), f"{path}.items[{index}].alt", errors, non_empty=True)
            if item.get("caption") is not None:
                validate_inline(item.get("caption"), f"{path}.items[{index}].caption", errors)
            kind = item.get("kind")
            if kind is not None and kind not in {"png", "jpg", "jpeg", "gif", "webp"}:
                errors.append(f"{path}.items[{index}].kind is unsupported")
    elif block_type == "columns":
        columns = require_array("columns")
        if len(columns) < 2:
            errors.append(f"{path}.columns must contain at least 2 columns")
        for column_index, column in enumerate(columns):
            if not is_object(column):
                errors.append(f"{path}.columns[{column_index}] must be an object")
                continue
            if column.get("title") is not None:
                validate_localized_string(column.get("title"), f"{path}.columns[{column_index}].title", errors)
            for block_index, child in enumerate(as_list(column.get("blocks"))):
                validate_block(child, f"{path}.columns[{column_index}].blocks[{block_index}]", errors)
            if column.get("content") is not None:
                validate_inline(column.get("content"), f"{path}.columns[{column_index}].content", errors)
    elif block_type == "toggle-view":
        views = require_array("views")
        if len(views) < 2:
            errors.append(f"{path}.views must contain at least 2 views")
        ids: set[str] = set()
        default_view = block.get("defaultView")
        if default_view is not None and (not isinstance(default_view, str) or not SAFE_NAME_RE.match(default_view)):
            errors.append(f"{path}.defaultView must be a safe kebab-case id")
        for view_index, view in enumerate(views):
            if not is_object(view):
                errors.append(f"{path}.views[{view_index}] must be an object")
                continue
            view_id = view.get("id")
            if not isinstance(view_id, str) or not SAFE_NAME_RE.match(view_id):
                errors.append(f"{path}.views[{view_index}].id must be safe kebab-case")
            elif view_id in ids:
                errors.append(f"{path}.views[{view_index}].id is duplicated")
            else:
                ids.add(view_id)
            validate_localized_string(view.get("label"), f"{path}.views[{view_index}].label", errors, non_empty=True)
            for block_index, child in enumerate(as_list(view.get("blocks"))):
                validate_block(child, f"{path}.views[{view_index}].blocks[{block_index}]", errors)
        if isinstance(default_view, str) and ids and default_view not in ids:
            errors.append(f"{path}.defaultView must match a view id")
    elif block_type == "slider":
        validate_localized_string(block.get("label"), f"{path}.label", errors, non_empty=True)
        if block.get("description") is not None:
            validate_inline(block.get("description"), f"{path}.description", errors)
        for key in ("min", "max", "value"):
            number = block.get(key)
            if not isinstance(number, (int, float)) or isinstance(number, bool):
                errors.append(f"{path}.{key} must be a number")
        step = block.get("step", 1)
        if not isinstance(step, (int, float)) or isinstance(step, bool) or step <= 0:
            errors.append(f"{path}.step must be a positive number")
        minimum = block.get("min")
        maximum = block.get("max")
        value = block.get("value")
        if isinstance(minimum, (int, float)) and isinstance(maximum, (int, float)) and minimum >= maximum:
            errors.append(f"{path}.min must be less than max")
        if (
            isinstance(minimum, (int, float))
            and isinstance(maximum, (int, float))
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and not minimum <= value <= maximum
        ):
            errors.append(f"{path}.value must be between min and max")
        unit = block.get("unit")
        if unit is not None and not isinstance(unit, str):
            errors.append(f"{path}.unit must be a string")
        validate_inline(block.get("target"), f"{path}.target", errors)
        if block.get("effect", "opacity") != "opacity":
            errors.append(f"{path}.effect is unsupported")
    elif block_type == "chapter-list":
        for index, item in enumerate(require_array("items")):
            if not is_object(item):
                errors.append(f"{path}.items[{index}] must be an object")
                continue
            if not isinstance(item.get("href"), str) or href_kind(item.get("href")) != "relative":
                errors.append(f"{path}.items[{index}].href must be a relative path")
            if item.get("number") is not None:
                validate_localized_string(item.get("number"), f"{path}.items[{index}].number", errors)
            if item.get("icon") is not None and (not isinstance(item.get("icon"), str) or not item.get("icon").strip()):
                errors.append(f"{path}.items[{index}].icon must be a non-empty string")
            validate_localized_string(item.get("title"), f"{path}.items[{index}].title", errors, non_empty=True)
            if item.get("description") is not None:
                validate_inline(item.get("description"), f"{path}.items[{index}].description", errors)
    else:
        errors.append(f"{path}.type is unknown: {block_type}")


def validate_document(doc: Any, config_dir: Path = CONFIG_DIR) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    if not is_object(doc):
        return ValidationResult(["document must be a JSON object"], warnings)

    metadata = doc.get("metadata")
    manifest = doc.get("manifest")
    sections = doc.get("sections")

    if not is_object(metadata):
        errors.append("metadata must be an object")
        metadata = {}
    if not is_object(manifest):
        errors.append("manifest must be an object")
        manifest = {}
    if not isinstance(sections, list) or not sections:
        errors.append("sections must be a non-empty array")
        sections = []

    if not isinstance(metadata.get("title"), str) or not metadata.get("title"):
        if not is_localized_object(metadata.get("title")):
            errors.append("metadata.title must be a non-empty string")
        else:
            validate_localized_string(metadata.get("title"), "metadata.title", errors, non_empty=True)
    if metadata.get("language") not in {"zh-CN", "en"}:
        errors.append("metadata.language must be zh-CN or en")
    locales = metadata.get("locales")
    if locales is not None:
        if not isinstance(locales, list) or not locales:
            errors.append("metadata.locales must be a non-empty array")
        else:
            seen_locales: set[str] = set()
            for index, locale in enumerate(locales):
                if locale not in set(SUPPORTED_LOCALES):
                    errors.append(f"metadata.locales[{index}] must be zh-CN or en")
                elif locale in seen_locales:
                    errors.append(f"metadata.locales[{index}] is duplicated: {locale}")
                else:
                    seen_locales.add(locale)
    validate_shell_links(metadata, errors)
    validate_logo(metadata, errors)

    document_types = {item["id"]: item for item in load_config("document-types.json", config_dir)["documentTypes"]}
    scenarios = {item["id"]: item for item in load_config("scenario-skeletons.json", config_dir)["scenarios"]}
    components = {item["id"]: item for item in load_config("components.json", config_dir)["components"]}

    document_type = manifest.get("documentType")
    scenario = manifest.get("scenario")
    if document_type not in document_types:
        errors.append(f"manifest.documentType is unknown: {document_type}")
    if scenario not in scenarios and scenario != "none":
        errors.append(f"manifest.scenario is unknown: {scenario}")

    manifest_sections = as_list(manifest.get("sections"))
    if not all(isinstance(item, str) for item in manifest_sections):
        errors.append("manifest.sections must be an array of strings")

    actual_section_ids: list[str] = []
    for section_index, section in enumerate(sections):
        path = f"sections[{section_index}]"
        if not is_object(section):
            errors.append(f"{path} must be an object")
            continue
        section_id = section.get("id")
        if not isinstance(section_id, str) or not SECTION_ID_RE.match(section_id):
            errors.append(f"{path}.id must be safe kebab-case")
        else:
            actual_section_ids.append(section_id)
        validate_localized_string(section.get("title"), f"{path}.title", errors, non_empty=True)
        blocks = section.get("blocks")
        if not isinstance(blocks, list):
            errors.append(f"{path}.blocks must be an array")
            continue
        for block_index, block in enumerate(blocks):
            validate_block(block, f"{path}.blocks[{block_index}]", errors)

    if manifest_sections and actual_section_ids and manifest_sections != actual_section_ids:
        errors.append("manifest.sections must match sections[].id in order")

    if scenario in scenarios:
        required_sections = scenarios[scenario].get("requiredSections", [])
        if manifest_sections != required_sections:
            errors.append(f"manifest.sections must match scenario '{scenario}' requiredSections")

    component_groups = manifest.get("components", {})
    if not is_object(component_groups):
        errors.append("manifest.components must be an object")
        component_groups = {}
    for group in ("required", "optional", "omitted"):
        values = component_groups.get(group)
        if not isinstance(values, list):
            errors.append(f"manifest.components.{group} must be an array")
            continue
        for item in values:
            if item not in components:
                errors.append(f"manifest.components.{group} contains unknown component: {item}")

    found_block_types: set[str] = set()
    for section in sections:
        if is_object(section):
            collect_block_types(as_list(section.get("blocks")), found_block_types)
    known_block_types: set[str] = set()
    for component in components.values():
        known_block_types.update(component.get("blockTypes", []))
    for block_type in sorted(found_block_types - known_block_types):
        errors.append(f"no registered component handles block type: {block_type}")

    if not errors and scenario in scenarios:
        scenario_required = set(scenarios[scenario].get("requiredComponents", []))
        declared = set(component_groups.get("required", [])) | set(component_groups.get("optional", []))
        missing = sorted(scenario_required - declared)
        if missing:
            warnings.append(f"scenario '{scenario}' required components not declared: {', '.join(missing)}")

    return ValidationResult(errors, warnings)


def metadata_line(metadata: dict[str, Any], ctx: RenderContext | None = None) -> str:
    parts: list[str] = []
    owner = metadata.get("owner")
    updated_at = metadata.get("updatedAt")
    if isinstance(owner, str) and owner and owner != "unknown":
        parts.append(f"{render_i18n_text(ctx, 'metadata.owner', 'Owner')} {render_text(owner, ctx)}")
    if isinstance(updated_at, str) and updated_at:
        parts.append(f"{render_i18n_text(ctx, 'metadata.updated', 'Updated')} {esc(updated_at)}")
    return " · ".join(parts)


def render_summary_block(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    items = []
    for item in as_list(block.get("items")):
        if is_object(item):
            items.append(f"<li><strong>{render_text(item.get('label'), ctx)}:</strong> {render_inline(item.get('body'), ctx)}</li>")
    return f"<section class=\"doc-summary\"><ul>{''.join(items)}</ul></section>"


def render_paragraph(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    return f"<p>{render_inline(block.get('text'), ctx)}</p>"


def render_list(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    tag = "ol" if block.get("ordered") else "ul"
    items = "".join(f"<li>{render_inline(item, ctx)}</li>" for item in as_list(block.get("items")))
    return f"<{tag}>{items}</{tag}>"


def render_callout(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    variant = block.get("variant", "info")
    cls = {
        "info": "callout callout-info",
        "warning": "callout callout-warning",
        "danger": "callout callout-danger",
        "success": "callout callout-success",
    }.get(variant, "callout callout-info")
    title = block.get("title")
    title_html = f"<strong>{render_text(title, ctx)}</strong>" if title else ""
    return (
        f"<aside class=\"{cls}\">"
        f"{title_html}<p>{render_inline(block.get('body'), ctx)}</p>"
        "</aside>"
    )


def render_table(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    header_cells = "".join(f"<th>{render_text(header, ctx)}</th>" for header in as_list(block.get("headers")))
    rows = ["<tr>" + "".join(f"<td>{render_inline(cell, ctx)}</td>" for cell in row) + "</tr>"
            for row in as_list(block.get("rows")) if isinstance(row, list)]
    body = ("\n" + "\n".join(rows)) if rows else ""
    return f"<table>\n<tr>{header_cells}</tr>{body}\n</table>"


def render_details(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    open_attr = " open" if block.get("open") else ""
    body = "".join(render_block(child, ctx) for child in as_list(block.get("blocks")) if is_object(child))
    return f"<details class=\"details-block\"{open_attr}><summary>{render_text(block.get('summary'), ctx)}</summary>{body}</details>"


def code_shell_id(ctx: RenderContext | None, language: Any, code: Any, extra: str = "") -> str:
    if ctx is not None:
        ctx.code_index += 1
        return f"code-{ctx.code_index}"
    raw = f"{text(language)}\0{text(code)}\0{extra}".encode("utf-8")
    return "code-" + hashlib.sha1(raw).hexdigest()[:12]


def code_scheme(language: Any, source: Any, ctx: RenderContext | None = None) -> dict[str, str]:
    lang = text(language).strip().lower()
    source_text = text(source)
    scheme = {
        "json": {"label": "JSON", "class": "code-scheme-json"},
        "javascript": {"label": "JS", "class": "code-scheme-js"},
        "js": {"label": "JS", "class": "code-scheme-js"},
        "typescript": {"label": "TS", "class": "code-scheme-ts"},
        "ts": {"label": "TS", "class": "code-scheme-ts"},
        "shell": {"label": "Shell", "class": "code-scheme-shell"},
        "bash": {"label": "Shell", "class": "code-scheme-shell"},
        "python": {"label": "Python", "class": "code-scheme-python"},
        "py": {"label": "Python", "class": "code-scheme-python"},
        "text": {"label": "Text", "class": "code-scheme-text"},
    }.get(lang, {"label": text(language).upper() or tr(ctx, "code.text", "Text"), "class": "code-scheme-text"})
    status = ""
    status_class = ""
    if lang == "json":
        try:
            json.loads(source_text)
            status = tr(ctx, "code.jsonValid", "Valid JSON")
            status_class = "code-status-ok"
        except json.JSONDecodeError:
            status = tr(ctx, "code.jsonInvalid", "Invalid JSON")
            status_class = "code-status-error"
    return {**scheme, "status": status, "statusClass": status_class}


def render_code_rows(source: Any, scheme_class: str = "code-scheme-text") -> str:
    lines = text(source).splitlines() or [""]
    rows = []
    for index, line in enumerate(lines, start=1):
        rows.append(
            "<span class=\"code-line\">"
            f"<span class=\"code-line-number\" aria-hidden=\"true\">{index}</span>"
            f"<span class=\"code-line-content\">{render_code_tokens(line, scheme_class)}</span>"
            "</span>"
        )
    return "".join(rows)


def render_code_tokens(line: str, scheme_class: str) -> str:
    if scheme_class == "code-scheme-json":
        escaped = esc(line)
        escaped = re.sub(r'(&quot;[^&]*?&quot;)(\s*:)', r'<span class="code-token-key">\1</span>\2', escaped)
        escaped = re.sub(r'\b(true|false|null)\b', r'<span class="code-token-bool">\1</span>', escaped)
        escaped = re.sub(r'(?<![\w.-])(-?\d+(?:\.\d+)?)\b', r'<span class="code-token-number">\1</span>', escaped)
        return escaped
    if scheme_class == "code-scheme-shell":
        escaped = esc(line)
        escaped = re.sub(r'(^|\s)(--[A-Za-z0-9][A-Za-z0-9_-]*)', r'\1<span class="code-token-flag">\2</span>', escaped)
        return escaped
    return esc(line)


def render_code_shell(
    code: Any,
    ctx: RenderContext | None = None,
    *,
    language: Any = "",
    shell_class: str = "code-block",
    extra_id: str = "",
) -> str:
    source = localized_value(code, default_locale_for_context(ctx))
    code_id = code_shell_id(ctx, language, source, extra_id)
    lang = text(language).strip()
    lang_attr = f" data-language=\"{attr(lang)}\"" if lang else ""
    scheme = code_scheme(lang, source, ctx)
    label = esc(scheme["label"])
    if is_localized_object(code) and ctx is not None and len(ctx.locales) > 1:
        body = []
        for locale in ctx.locales:
            active = "true" if locale == ctx.active_locale else "false"
            body.append(
                f"<span data-locale=\"{attr(locale)}\" data-locale-active=\"{active}\">"
                f"{render_code_rows(localized_value(code, locale, ctx.active_locale), scheme['class'])}"
                "</span>"
            )
        rows = "".join(body)
    else:
        rows = render_code_rows(source, scheme["class"])
    status_html = ""
    if scheme["status"]:
        status_class = f" {attr(scheme['statusClass'])}" if scheme["statusClass"] else ""
        status_html = f"<span class=\"code-status{status_class}\">{esc(scheme['status'])}</span>"
    return (
        f"<section class=\"code-shell {attr(shell_class)} {attr(scheme['class'])}\">"
        "<div class=\"code-header\">"
        f"<span class=\"code-language\">{label}</span>"
        f"{status_html}"
        f"<button class=\"code-copy\" type=\"button\" data-copy-target=\"{attr(code_id)}\" "
        f"data-i18n-key=\"code.copy\">{esc(tr(ctx, 'code.copy', 'Copy'))}</button>"
        "</div>"
        f"<pre class=\"code-pre\"{lang_attr}><code id=\"{attr(code_id)}\"{lang_attr}>{rows}</code></pre>"
        "</section>"
    )


def render_code(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    return render_code_shell(block.get("code"), ctx, language=block.get("language", ""), shell_class="code-block")


def svg_text(value: Any) -> str:
    return html.escape(text(value), quote=False)


def render_sequence_svg(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    steps = as_list(block.get("source", {}).get("steps"))
    participants: list[Any] = []
    participant_keys: set[str] = set()
    for step in steps:
        if not is_object(step):
            continue
        for key in ("from", "to"):
            participant = step.get(key)
            participant_key = text(localized_value(participant, "en"))
            if participant_key and participant_key not in participant_keys:
                participant_keys.add(participant_key)
                participants.append(participant)
    width = max(620, 180 * max(1, len(participants)) + 120)
    top = 94
    row_height = 58
    height = max(260, top + 44 + row_height * len(steps))
    lane_by_key = {
        text(localized_value(participant, "en")): 80 + index * 180
        for index, participant in enumerate(participants)
    }
    defs = (
        "<defs><marker id=\"seq-arrow\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" markerWidth=\"7\" markerHeight=\"7\" orient=\"auto\">"
        "<path d=\"M0 0 L10 5 L0 10z\" fill=\"#8a929b\"></path></marker></defs>"
    )
    rows = [defs]
    lifeline_bottom = height - 24
    for participant in participants:
        key = text(localized_value(participant, "en"))
        x = lane_by_key.get(key, 80)
        rows.append(f"<rect x=\"{x - 56}\" y=\"22\" width=\"112\" height=\"34\" rx=\"7\" fill=\"#f3f4f4\" stroke=\"#9aa1a8\"></rect>")
        rows.append(render_svg_text_variants(participant, ctx, f"x=\"{x}\" y=\"44\" text-anchor=\"middle\" font-size=\"13\" fill=\"#2f3439\""))
        rows.append(f"<line x1=\"{x}\" y1=\"56\" x2=\"{x}\" y2=\"{lifeline_bottom}\" stroke=\"#9aa1a8\" stroke-width=\"1\" stroke-dasharray=\"5 5\"></line>")
    for index, step in enumerate(steps):
        if not is_object(step):
            continue
        from_key = text(localized_value(step.get("from"), "en"))
        to_key = text(localized_value(step.get("to"), "en"))
        x1 = lane_by_key.get(from_key, 80)
        x2 = lane_by_key.get(to_key, x1 + 180)
        y = top + index * row_height
        label_y = y - 9
        rows.append(f"<line x1=\"{x1}\" y1=\"{y}\" x2=\"{x2}\" y2=\"{y}\" stroke=\"#8a929b\" stroke-width=\"2\" marker-end=\"url(#seq-arrow)\"></line>")
        rows.append(render_svg_text_variants(step.get("label"), ctx, f"x=\"{(x1 + x2) / 2:.0f}\" y=\"{label_y}\" text-anchor=\"middle\" font-size=\"12\" fill=\"#68717b\""))
        rows.append(f"<rect x=\"{x2 - 4}\" y=\"{y - 8}\" width=\"8\" height=\"26\" rx=\"3\" fill=\"#dce8f8\" stroke=\"#9aa1a8\"></rect>")
    aria = localized_value(block.get("title") or tr(ctx, "diagram.sequenceAria", "Sequence diagram"), default_locale_for_context(ctx))
    return f"<svg viewBox=\"0 0 {width} {height}\" xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-label=\"{attr(aria)}\">{''.join(rows)}</svg>"


def render_flow_svg(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    source = block.get("source", {})
    nodes = as_list(source.get("nodes"))
    width = max(420, 220 * len(nodes))
    height = 180
    node_by_id = {node.get("id"): index for index, node in enumerate(nodes) if is_object(node)}
    defs = (
        "<defs><marker id=\"arrow\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" markerWidth=\"7\" markerHeight=\"7\" orient=\"auto\">"
        "<path d=\"M0 0 L10 5 L0 10z\" fill=\"#8a929b\"></path></marker></defs>"
    )
    parts = [defs]
    for edge in as_list(source.get("edges")):
        if not is_object(edge):
            continue
        start = node_by_id.get(edge.get("from"))
        end = node_by_id.get(edge.get("to"))
        if start is None or end is None:
            continue
        x1 = 80 + start * 220 + 120
        x2 = 80 + end * 220
        parts.append(f"<line x1=\"{x1}\" y1=\"82\" x2=\"{x2}\" y2=\"82\" stroke=\"#8a929b\" stroke-width=\"2\" marker-end=\"url(#arrow)\"></line>")
        if edge.get("label"):
            parts.append(render_svg_text_variants(edge.get("label"), ctx, f"x=\"{(x1 + x2) / 2:.0f}\" y=\"66\" text-anchor=\"middle\" font-size=\"12\" fill=\"#68717b\""))
    for index, node in enumerate(nodes):
        if not is_object(node):
            continue
        x = 80 + index * 220
        parts.append(f"<rect x=\"{x}\" y=\"54\" width=\"120\" height=\"56\" rx=\"7\" fill=\"#f3f4f4\" stroke=\"#9aa1a8\"></rect>")
        parts.append(render_svg_text_variants(node.get("label"), ctx, f"x=\"{x + 60}\" y=\"87\" text-anchor=\"middle\" font-size=\"13\" fill=\"#2f3439\""))
    aria = localized_value(block.get("title") or tr(ctx, "diagram.flowAria", "Flow diagram"), default_locale_for_context(ctx))
    return f"<svg viewBox=\"0 0 {width} {height}\" xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-label=\"{attr(aria)}\">{''.join(parts)}</svg>"


def render_er_svg(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    source = block.get("source", {})
    entities = [entity for entity in as_list(source.get("entities")) if is_object(entity)]
    width = max(760, 260 * len(entities) + 80)
    entity_width = 210
    card_tops: dict[str, tuple[int, int, int]] = {}
    heights = []
    for entity in entities:
        heights.append(66 + 24 * len(as_list(entity.get("fields"))))
    height = max(220, max(heights, default=120) + 96)
    defs = (
        "<defs><marker id=\"er-arrow\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" markerWidth=\"7\" markerHeight=\"7\" orient=\"auto\">"
        "<path d=\"M0 0 L10 5 L0 10z\" fill=\"#8a929b\"></path></marker></defs>"
    )
    parts = [defs]
    for index, entity in enumerate(entities):
        x = 44 + index * 260
        y = 46
        entity_height = 66 + 24 * len(as_list(entity.get("fields")))
        entity_id = text(entity.get("id"))
        card_tops[entity_id] = (x, y, entity_height)
        parts.append(f"<rect x=\"{x}\" y=\"{y}\" width=\"{entity_width}\" height=\"{entity_height}\" rx=\"8\" fill=\"#f3f4f4\" stroke=\"#9aa1a8\"></rect>")
        parts.append(f"<rect x=\"{x}\" y=\"{y}\" width=\"{entity_width}\" height=\"38\" rx=\"8\" fill=\"#dce8f8\" stroke=\"#9aa1a8\"></rect>")
        parts.append(render_svg_text_variants(entity.get("name"), ctx, f"x=\"{x + 16}\" y=\"{y + 25}\" font-size=\"14\" fill=\"#2f3439\""))
        for field_index, field in enumerate(as_list(entity.get("fields"))):
            parts.append(render_svg_text_variants(field, ctx, f"x=\"{x + 16}\" y=\"{y + 60 + field_index * 24}\" font-size=\"12\" fill=\"#68717b\""))
    for relationship in as_list(source.get("relationships")):
        if not is_object(relationship):
            continue
        start = card_tops.get(text(relationship.get("from")))
        end = card_tops.get(text(relationship.get("to")))
        if not start or not end:
            continue
        x1, y1, h1 = start
        x2, y2, h2 = end
        sx = x1 + entity_width
        ex = x2
        sy = y1 + h1 + 30
        ey = y2 + h2 + 30
        bend_y = max(sy, ey) + 18
        parts.append(f"<polyline points=\"{sx},{sy} {sx},{bend_y} {ex},{bend_y} {ex},{ey}\" fill=\"none\" stroke=\"#8a929b\" stroke-width=\"2\" marker-end=\"url(#er-arrow)\"></polyline>")
        if relationship.get("label"):
            parts.append(render_svg_text_variants(relationship.get("label"), ctx, f"x=\"{(sx + ex) / 2:.0f}\" y=\"{bend_y - 8}\" text-anchor=\"middle\" font-size=\"12\" fill=\"#68717b\""))
    aria = localized_value(block.get("title") or tr(ctx, "diagram.erAria", "Entity relationship diagram"), default_locale_for_context(ctx))
    return f"<svg viewBox=\"0 0 {width} {height}\" xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-label=\"{attr(aria)}\">{''.join(parts)}</svg>"


def render_diagram(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    source = block.get("source", {})
    fmt = source.get("format")
    if fmt == "structured-sequence":
        svg = render_sequence_svg(block, ctx)
    elif fmt == "structured-flow":
        svg = render_flow_svg(block, ctx)
    elif fmt == "structured-er":
        svg = render_er_svg(block, ctx)
    elif fmt == "svg":
        svg = text(source.get("content"))
    else:
        svg = f"<svg viewBox=\"0 0 320 100\" xmlns=\"http://www.w3.org/2000/svg\"><text x=\"20\" y=\"50\">{esc(tr(ctx, 'diagram.unsupported', 'Unsupported diagram'))}</text></svg>"
    name = attr(block.get("downloadName") or "diagram")
    title = block.get("title")
    caption = f"<figcaption>{render_text(title, ctx)}</figcaption>" if title else ""
    return f"<figure class=\"diagram\" data-download-name=\"{name}\">{caption}{svg}</figure>"


def render_diff(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    def side_html(side: dict[str, Any]) -> str:
        rows = []
        marker_by_kind = {"add": "+", "remove": "-", "warning": "!", "context": " "}
        for index, line in enumerate(as_list(side.get("lines")), start=1):
            if is_object(line):
                kind = line.get("kind", "context")
                highlight = " line-highlight" if line.get("highlight") else ""
                rows.append(
                    f"<div class=\"diff-line line-{attr(kind)}{highlight}\">"
                    f"<span class=\"diff-line-number\" aria-hidden=\"true\">{index}</span>"
                    f"<span class=\"diff-line-marker\" aria-hidden=\"true\">{marker_by_kind.get(kind, ' ')}</span>"
                    f"<span class=\"diff-line-content\">{render_text(line.get('text'), ctx)}</span>"
                    "</div>"
                )
        lang = text(side.get("language")).strip()
        lang_attr = f" data-language=\"{attr(lang)}\"" if lang else ""
        return f"<div class=\"diff-side\"><h3>{render_text(side.get('label'), ctx)}</h3><div class=\"diff-code\"{lang_attr}>{''.join(rows)}</div></div>"

    left = side_html(block.get("left", {}))
    right = side_html(block.get("right", {}))
    title = f"<h3>{render_text(block.get('title'), ctx)}</h3>" if block.get("title") else ""
    return f"<section class=\"diff-block\">{title}{left}{right}</section>"


def render_participants(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    cards = []
    for item in as_list(block.get("items")):
        if not is_object(item):
            continue
        role = f"<p><em>{render_text(item.get('role'), ctx)}</em></p>" if item.get("role") else ""
        cards.append(f"<div class=\"participant-card\"><h3>{render_text(item.get('name'), ctx)}</h3>{role}<p>{render_inline(item.get('responsibility'), ctx)}</p></div>")
    return f"<section class=\"participants\">{''.join(cards)}</section>"


def render_source_refs(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    items = []
    for item in as_list(block.get("items")):
        if not is_object(item):
            continue
        href = attr(item.get("url"))
        label = render_text(item.get("label"), ctx)
        note = f" - {render_text(item.get('text'), ctx)}" if item.get("text") else ""
        target = " target=\"_blank\" rel=\"noopener noreferrer\"" if href.startswith(("http://", "https://")) else ""
        items.append(f"<li><a href=\"{href}\"{target}>{label}</a>{note}</li>")
    return f"<ul class=\"source-refs\">{''.join(items)}</ul>"


def render_files(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    items = []
    for item in as_list(block.get("items")):
        if not is_object(item):
            continue
        path = esc(item.get("path"))
        line = f":{esc(item.get('lineStart'))}" if item.get("lineStart") else ""
        note = f" - {render_text(item.get('note'), ctx)}" if item.get("note") else ""
        if item.get("url"):
            items.append(f"<li><a href=\"{attr(item.get('url'))}\">{path}{line}</a>{note}</li>")
        else:
            items.append(f"<li><code>{path}{line}</code>{note}</li>")
    return f"<ul class=\"files\">{''.join(items)}</ul>"


def render_action(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    prompt = render_code_shell(
        block.get("prompt"),
        ctx,
        language="shell",
        shell_class="prompt-block",
        extra_id=text(block.get("title")),
    ) if block.get("prompt") else ""
    return f"<section class=\"action-card\"><h3>{render_text(block.get('title'), ctx)}</h3><p>{render_inline(block.get('description'), ctx)}</p>{prompt}</section>"


def render_values_grid(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    cards = []
    for item in as_list(block.get("items")):
        if is_object(item):
            cards.append(f"<div class=\"value-card\"><h3>{render_text(item.get('title'), ctx)}</h3><p>{render_inline(item.get('body'), ctx)}</p></div>")
    return f"<section class=\"values-grid\">{''.join(cards)}</section>"


def render_acceptance_criteria(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    items = "".join(f"<li>{render_inline(item, ctx)}</li>" for item in as_list(block.get("items")))
    return f"<ol class=\"acceptance-criteria\">{items}</ol>"


def render_open_questions(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    items = "".join(
        f"<li class=\"open-question\"><span class=\"open-question-marker\">Q{index}</span><span class=\"open-question-text\">{render_inline(item, ctx)}</span></li>"
        for index, item in enumerate(as_list(block.get("questions")), start=1)
    )
    title = render_text(block.get("title"), ctx) if block.get("title") is not None else render_i18n_text(ctx, "openQuestions.title", "Open questions")
    count = len(as_list(block.get("questions")))
    return (
        "<section class=\"open-questions-block\">"
        "<header class=\"open-questions-header\">"
        "<div class=\"open-questions-heading\">"
        f"<span class=\"open-questions-kicker\">{render_i18n_text(ctx, 'openQuestions.kicker', 'Unresolved')}</span>"
        f"<h3 class=\"open-questions-title\">{title}</h3>"
        "</div>"
        f"<span class=\"open-questions-count\">{count} {render_i18n_text(ctx, 'openQuestions.count', 'questions')}</span>"
        "</header>"
        f"<ul class=\"open-questions\">{items}</ul>"
        "</section>"
    )


def render_media(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    figures = []
    for item in as_list(block.get("items")):
        if not is_object(item):
            continue
        src = attr(item.get("src"))
        alt = attr(localized_value(item.get("alt"), default_locale_for_context(ctx)))
        kind = text(item.get("kind")).upper()
        kind_html = f"<span class=\"media-kind\">{esc(kind)}</span>" if kind else ""
        caption = render_inline(item.get("caption"), ctx) if item.get("caption") is not None else render_text(item.get("alt"), ctx)
        figures.append(
            "<figure class=\"media-frame\">"
            f"<img src=\"{src}\" alt=\"{alt}\" loading=\"eager\"/>"
            f"<figcaption>{kind_html}{caption}</figcaption>"
            "</figure>"
        )
    return f"<section class=\"media-grid\">{''.join(figures)}</section>"


def render_columns(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    columns = []
    for column in as_list(block.get("columns")):
        if not is_object(column):
            continue
        title = f"<h3>{render_text(column.get('title'), ctx)}</h3>" if column.get("title") else ""
        content = f"<p>{render_inline(column.get('content'), ctx)}</p>" if column.get("content") is not None else ""
        body = content + "".join(render_block(child, ctx) for child in as_list(column.get("blocks")) if is_object(child))
        columns.append(f"<div class=\"column\">{title}{body}</div>")
    return f"<section class=\"columns\">{''.join(columns)}</section>"


def render_toggle_view(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    views = [view for view in as_list(block.get("views")) if is_object(view)]
    if not views:
        return ""
    default_view = text(block.get("defaultView") or views[0].get("id"))
    if ctx is not None:
        ctx.code_index += 1
        group_id = f"view-{ctx.code_index}"
    else:
        group_id = "view-" + hashlib.sha1(json.dumps(block, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:10]
    buttons = []
    panels = []
    for view in views:
        view_id = text(view.get("id"))
        target_id = f"{group_id}-{view_id}"
        active = view_id == default_view
        buttons.append(
            f"<button class=\"toggle-button\" type=\"button\" data-view-target=\"{attr(target_id)}\" "
            f"aria-pressed=\"{'true' if active else 'false'}\">{render_text(view.get('label'), ctx)}</button>"
        )
        body = "".join(render_block(child, ctx) for child in as_list(view.get("blocks")) if is_object(child))
        panels.append(
            f"<div class=\"toggle-panel\" data-view-panel=\"{attr(target_id)}\" data-view-active=\"{'true' if active else 'false'}\">"
            f"{body}</div>"
        )
    return (
        f"<section class=\"toggle-view\" data-view-group=\"{attr(group_id)}\">"
        f"<div class=\"toggle-toolbar\" role=\"group\">{''.join(buttons)}</div>"
        f"{''.join(panels)}"
        "</section>"
    )


def render_slider(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    if ctx is not None:
        ctx.code_index += 1
        slider_id = f"slider-{ctx.code_index}"
    else:
        slider_id = "slider-" + hashlib.sha1(json.dumps(block, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:10]
    minimum = text(block.get("min", 0))
    maximum = text(block.get("max", 100))
    step = text(block.get("step", 1))
    value = text(block.get("value", block.get("min", 0)))
    unit = text(block.get("unit", ""))
    effect = text(block.get("effect", "opacity")) or "opacity"
    description = f"<p>{render_inline(block.get('description'), ctx)}</p>" if block.get("description") is not None else ""
    return (
        f"<section class=\"slider-control\" data-slider-demo=\"{attr(slider_id)}\" data-slider-effect=\"{attr(effect)}\">"
        "<div class=\"slider-header\">"
        f"<label for=\"{attr(slider_id)}\">{render_text(block.get('label'), ctx)}</label>"
        f"<output class=\"slider-value\" data-slider-output=\"{attr(slider_id)}\">{esc(value)}{esc(unit)}</output>"
        "</div>"
        f"{description}"
        f"<input class=\"slider-range\" id=\"{attr(slider_id)}\" type=\"range\" min=\"{attr(minimum)}\" max=\"{attr(maximum)}\" "
        f"step=\"{attr(step)}\" value=\"{attr(value)}\" data-slider-target=\"{attr(slider_id)}\" data-slider-unit=\"{attr(unit)}\">"
        f"<p class=\"slider-demo slider-target\" data-slider-demo=\"{attr(slider_id)}\">{render_inline(block.get('target'), ctx)}</p>"
        "</section>"
    )


def render_chapter_list(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    items = []
    for item in as_list(block.get("items")):
        if not is_object(item):
            continue
        number = item.get("number") or item.get("id")
        number_html = f"<span class=\"chapter-number\">{render_text(number, ctx)}</span>" if number else ""
        icon_html = render_chapter_icon(item.get("icon"))
        description_html = (
            f"<span class=\"chapter-description\">{render_inline(item.get('description'), ctx)}</span>"
            if item.get("description") is not None
            else ""
        )
        items.append(
            "<li class=\"chapter-card\">"
            f"<a href=\"{attr(item.get('href'))}\">"
            f"{icon_html}"
            f"{number_html}"
            "<span class=\"chapter-content\">"
            f"<span class=\"chapter-title\">{render_text(item.get('title'), ctx)}</span>"
            f"{description_html}"
            "</span>"
            "</a>"
            "</li>"
        )
    return f"<ul class=\"chapter-list\">{''.join(items)}</ul>"


RENDERER_REGISTRY: dict[str, Any] = {
    "summary": render_summary_block,
    "paragraph": render_paragraph,
    "list": render_list,
    "callout": render_callout,
    "table": render_table,
    "details": render_details,
    "code": render_code,
    "diagram": render_diagram,
    "diff": render_diff,
    "participants": render_participants,
    "sourceRefs": render_source_refs,
    "files": render_files,
    "actionCard": render_action,
    "valuesGrid": render_values_grid,
    "acceptanceCriteria": render_acceptance_criteria,
    "openQuestions": render_open_questions,
    "media": render_media,
    "columns": render_columns,
    "toggleView": render_toggle_view,
    "slider": render_slider,
    "chapterList": render_chapter_list,
}


_BLOCK_RENDERER_MAP_CACHE: dict[str, dict[str, Any]] = {}


def build_block_type_renderer_map(config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    key = str(config_dir)
    cached = _BLOCK_RENDERER_MAP_CACHE.get(key)
    if cached is not None:
        return cached
    config = load_config("components.json", config_dir)
    out: dict[str, Any] = {}
    for component in config.get("components", []):
        if not is_object(component):
            continue
        renderer_id = component.get("renderer")
        if not isinstance(renderer_id, str):
            continue
        fn = RENDERER_REGISTRY.get(renderer_id)
        if fn is None:
            continue
        for block_type in as_list(component.get("blockTypes")):
            if isinstance(block_type, str):
                out[block_type] = fn
    _BLOCK_RENDERER_MAP_CACHE[key] = out
    return out


def render_block(block: dict[str, Any], ctx: RenderContext | None = None) -> str:
    renderers = build_block_type_renderer_map(ctx.config_dir if ctx else CONFIG_DIR)
    renderer = renderers.get(block.get("type"))
    if not renderer:
        return f"<p class=\"section-empty\">{esc(tr(ctx, 'state.unsupportedBlock', 'Unsupported block'))}: {esc(block.get('type'))}</p>"
    return renderer(block, ctx)


def block_types_in_doc(doc: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for section in as_list(doc.get("sections")):
        if is_object(section):
            collect_block_types(as_list(section.get("blocks")), found)
    return found


def load_layout(layout_id: str = "single-doc", config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    config = load_config("layouts.json", config_dir)
    layouts = {
        layout["id"]: layout
        for layout in config.get("layouts", [])
        if is_object(layout) and isinstance(layout.get("id"), str)
    }
    if layout_id not in layouts:
        raise CastDocsError(f"layout not found: {layout_id}")
    return layouts[layout_id]


def resolve_active_interactions(
    doc: dict[str, Any],
    layout: dict[str, Any],
    config_dir: Path = CONFIG_DIR,
) -> list[dict[str, Any]]:
    config = load_config("interactions.json", config_dir)
    specs = {
        spec["id"]: spec
        for spec in config.get("interactions", [])
        if is_object(spec) and isinstance(spec.get("id"), str)
    }
    default_ids = [iid for iid in as_list(layout.get("defaultInteractions")) if iid in specs]
    optional_ids = [iid for iid in as_list(layout.get("optionalInteractions")) if iid in specs]
    block_types = block_types_in_doc(doc)
    active: list[dict[str, Any]] = []
    seen: set[str] = set()
    for iid in default_ids + optional_ids:
        if iid in seen:
            continue
        seen.add(iid)
        spec = specs[iid]
        if iid in default_ids:
            triggered = True
        else:
            supported = {bt for bt in as_list(spec.get("supportedBlockTypes")) if isinstance(bt, str)}
            triggered = bool(supported and supported & block_types)
        if triggered:
            active.append(spec)
    return active


def render_toc(sections: list[dict[str, Any]], ctx: RenderContext | None = None) -> str:
    items = []
    for index, section in enumerate(sections, start=1):
        number = f"{index:02d}"
        items.append(f"<li><a href=\"#{attr(section.get('id'))}\"><span>{number}</span>{render_text(section.get('title'), ctx)}</a></li>")
    return f"<nav class=\"toc\" aria-label=\"{attr(tr(ctx, 'chrome.tocAria', 'Table of contents'))}\"><ol>{''.join(items)}</ol></nav>"


def render_document_set_sidebar(metadata: dict[str, Any], ctx: RenderContext | None = None) -> str:
    document_set = metadata.get("documentSet")
    if not is_object(document_set):
        return ""
    groups = []
    for group in as_list(document_set.get("sections")):
        if not is_object(group):
            continue
        chapters = []
        for chapter in as_list(group.get("chapters")):
            if not is_object(chapter):
                continue
            number = chapter.get("number") or chapter.get("id")
            chapters.append(
                f"<li><a href=\"{attr(chapter.get('href'))}\">"
                f"<span>{render_text(number, ctx)}</span>{render_text(chapter.get('title'), ctx)}</a></li>"
            )
        if chapters:
            groups.append(
                f"<li><a href=\"{attr(group.get('href') or '#')}\"><span></span>{render_text(group.get('label'), ctx)}</a>"
                f"<ol>{''.join(chapters)}</ol></li>"
            )
    if not groups:
        return ""
    title = document_set.get("title") or tr(ctx, "chrome.contents", "Contents")
    return (
        f"<p class=\"nav-title\">{render_text(title, ctx)}</p>"
        f"<nav class=\"toc\" aria-label=\"{attr(tr(ctx, 'chrome.tocAria', 'Table of contents'))}\"><ol>{''.join(groups)}</ol></nav>"
    )


def render_sidebar(sections: list[dict[str, Any]], ctx: RenderContext | None = None) -> str:
    if ctx is not None and ctx.metadata is not None:
        set_sidebar = render_document_set_sidebar(ctx.metadata, ctx)
        if set_sidebar:
            return set_sidebar
    toc = render_toc(sections, ctx)
    return f"<p class=\"nav-title\">{render_i18n_text(ctx, 'chrome.contents', 'Contents')}</p>{toc}"


def render_shell_links(metadata: dict[str, Any], placement: str, ctx: RenderContext | None = None) -> str:
    links = []
    for item in as_list(metadata.get("shellLinks")):
        if not is_object(item) or item.get("placement", "topbar") != placement:
            continue
        href = text(item.get("href"))
        target = " target=\"_blank\" rel=\"noopener noreferrer\"" if href.startswith(("http://", "https://")) else ""
        links.append(f"<a class=\"topbar-link\" href=\"{attr(href)}\"{target}>{render_text(item.get('label'), ctx)}</a>")
    if not links:
        return ""
    return f"<nav class=\"topbar-links\" data-slot=\"topbar-links\" aria-label=\"{attr(tr(ctx, 'chrome.documentLinksAria', 'Document links'))}\">{''.join(links)}</nav>"


def render_footer_links(metadata: dict[str, Any], ctx: RenderContext | None = None) -> str:
    links = []
    for item in as_list(metadata.get("shellLinks")):
        if not is_object(item) or item.get("placement") != "footer":
            continue
        href = text(item.get("href"))
        target = " target=\"_blank\" rel=\"noopener noreferrer\"" if href.startswith(("http://", "https://")) else ""
        links.append(f"<a href=\"{attr(href)}\"{target}>{render_text(item.get('label'), ctx)}</a>")
    return " · ".join(links)


def render_set_pagination(metadata: dict[str, Any], ctx: RenderContext | None = None) -> str:
    pagination = metadata.get("pagination")
    if not is_object(pagination):
        return ""

    def render_link(kind: str, label: str) -> str:
        item = pagination.get(kind)
        if not is_object(item):
            return "<span></span>"
        return (
            f"<a class=\"set-pagination-link set-pagination-{attr(kind)}\" href=\"{attr(item.get('href'))}\">"
            f"<span class=\"set-pagination-label\">{esc(label)}</span>"
            f"<span class=\"set-pagination-title\">{render_text(item.get('title'), ctx)}</span>"
            "</a>"
        )

    previous = render_link("prev", "Previous")
    next_item = render_link("next", "Next")
    if previous == "<span></span>" and next_item == "<span></span>":
        return ""
    return f"<nav class=\"set-pagination\" aria-label=\"Pagination\">{previous}{next_item}</nav>"


def image_to_data_uri(src: str, repo_root: Path = ROOT) -> str:
    if DATA_IMAGE_RE.match(src.strip()):
        return src.strip()
    if media_src_kind(src) != "relative":
        raise CastDocsError(f"unsupported logo image source: {src}")
    path = (repo_root / src).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise CastDocsError(f"logo image must stay inside the repository: {src}") from exc
    if not path.exists() or not path.is_file():
        raise CastDocsError(f"logo image not found: {src}")
    mime_type = mimetypes.guess_type(path.name)[0]
    if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
        raise CastDocsError(f"unsupported logo image type: {src}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def render_logo(metadata: dict[str, Any], ctx: RenderContext | None = None) -> str:
    logo = metadata.get("logo")
    if not is_object(logo):
        return ""
    src = logo.get("src")
    if not isinstance(src, str) or not src.strip():
        return ""
    img = (
        f"<img class=\"brand-logo-image\" src=\"{attr(image_to_data_uri(src, ctx.repo_root if ctx else ROOT))}\" "
        f"alt=\"{attr(localized_value(logo.get('alt', ''), default_locale_for_context(ctx), 'en'))}\" "
        "width=\"44\" height=\"44\" loading=\"eager\">"
    )
    href = logo.get("href")
    if isinstance(href, str) and href.strip():
        target = " target=\"_blank\" rel=\"noopener noreferrer\"" if href.startswith(("http://", "https://")) else ""
        label = localized_value(logo.get("alt", ""), default_locale_for_context(ctx), "en")
        return f"<a class=\"brand-logo\" href=\"{attr(href)}\" aria-label=\"{attr(label)}\"{target}>{img}</a>"
    return f"<span class=\"brand-logo\">{img}</span>"


def render_language_switcher(ctx: RenderContext) -> str:
    if len(ctx.locales) <= 1:
        return ""
    buttons = []
    for locale in ctx.locales:
        active = locale == ctx.active_locale
        buttons.append(
            f"<button class=\"locale-button\" type=\"button\" data-locale-target=\"{attr(locale)}\""
            f" aria-pressed=\"{'true' if active else 'false'}\">{esc(locale_display_label(ctx.i18n, locale))}</button>"
        )
    return (
        f"<div class=\"locale-switcher\" data-renderer-owned=\"true\" role=\"group\" "
        f"aria-label=\"{attr(tr(ctx, 'chrome.languageAria', 'Language'))}\">"
        f"{''.join(buttons)}</div>"
    )


def same_localized_text(left: Any, right: Any, ctx: RenderContext) -> bool:
    for locale in ctx.locales:
        if localized_value(left, locale, ctx.active_locale) != localized_value(right, locale, ctx.active_locale):
            return False
    return True


def render_topbar_title(metadata: dict[str, Any], title_value: Any, ctx: RenderContext, profile: ProjectProfile | None) -> str:
    parts: list[str] = []
    owner_name = project_owner_display_name(metadata, profile)
    if owner_name:
        parts.append(f"<span class=\"topbar-org\">{esc(owner_name)}</span>")
    project_name = project_display_name(profile)
    if project_name:
        parts.append(f"<span class=\"topbar-project\">{esc(project_name)}</span>")
    if not project_name or not same_localized_text(title_value, project_name, ctx):
        parts.append(f"<span class=\"topbar-doc\">{render_text(title_value, ctx)}</span>")
    if not parts:
        return render_text(title_value, ctx)
    return "<span class=\"topbar-breadcrumb\">" + "<span class=\"topbar-separator\" aria-hidden=\"true\">/</span>".join(parts) + "</span>"


def render_sections(sections: list[Any], ctx: RenderContext | None = None) -> str:
    rendered = []
    for section in sections:
        if not is_object(section):
            continue
        blocks_list = [render_block(block, ctx) for block in as_list(section.get("blocks")) if is_object(block)]
        if not blocks_list:
            blocks_list = [f"<p class=\"section-empty\">{esc(tr(ctx, 'state.noContent', 'No content.'))}</p>"]
        blocks_text = "\n".join(blocks_list)
        rendered.append(
            f"<section class=\"doc-section\" id=\"{attr(section.get('id'))}\">\n"
            f"<h2>{render_text(section.get('title'), ctx)}</h2>\n"
            f"{blocks_text}\n"
            "</section>"
        )
    return "\n\n".join(rendered)


THEME_COLOR_TO_CSS_VAR: dict[str, str] = {
    "bg": "--bg",
    "surface": "--surface",
    "surfaceSoft": "--soft",
    "text": "--text",
    "muted": "--muted",
    "faint": "--faint",
    "border": "--border",
    "primary": "--primary",
    "primarySoft": "--primary-soft",
    "accent": "--accent",
    "info": "--info",
    "infoSoft": "--info-soft",
    "warning": "--warn",
    "warningSoft": "--warn-soft",
    "danger": "--danger",
    "dangerSoft": "--danger-soft",
    "success": "--ok",
    "successSoft": "--ok-soft",
    "codeBg": "--code",
}


def _merge_theme(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(parent))
    overrides = child.get("overrides", {})
    if isinstance(overrides, dict):
        for dotted, value in overrides.items():
            keys = dotted.split(".")
            target = merged
            for key in keys[:-1]:
                target = target.setdefault(key, {})
            target[keys[-1]] = value
    return merged


def load_theme(theme_id: str = "cast-default", config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    config = load_config("theme-tokens.json", config_dir)
    themes = {theme["id"]: theme for theme in config.get("themes", []) if is_object(theme) and theme.get("id")}
    if theme_id not in themes:
        raise CastDocsError(f"theme not found: {theme_id}")
    theme = themes[theme_id]
    parent_id = theme.get("extends")
    if not parent_id:
        return theme
    if parent_id not in themes:
        raise CastDocsError(f"theme parent not found: {parent_id}")
    return _merge_theme(themes[parent_id], theme)


def compile_theme_root_css(theme: dict[str, Any]) -> str:
    modes = theme.get("modes", {})
    light_color = modes.get("light", {}).get("color", {}) if is_object(modes) else {}
    dark_color = modes.get("dark", {}).get("color", {}) if is_object(modes) else {}
    typography = theme.get("typography", {}) if is_object(theme.get("typography")) else {}

    def color_lines(color_map: dict[str, Any], indent: str) -> list[str]:
        lines = []
        for token, var in THEME_COLOR_TO_CSS_VAR.items():
            value = color_map.get(token) if is_object(color_map) else None
            if value:
                lines.append(f"{indent}{var}: {value};")
        return lines

    light_body = ["  color-scheme: light dark;", *color_lines(light_color, "  ")]
    sans = typography.get("sans")
    mono = typography.get("mono")
    if sans:
        light_body.append(f"  --sans: {sans};")
    if mono:
        light_body.append(f"  --mono: {mono};")
    size = typography.get("size")
    if is_object(size):
        for key, value in size.items():
            light_body.append(f"  --font-{key}: {value};")
    line_height = typography.get("lineHeight")
    if is_object(line_height):
        for key, value in line_height.items():
            light_body.append(f"  --line-{key}: {value};")
    weight = typography.get("weight")
    if is_object(weight):
        for key, value in weight.items():
            light_body.append(f"  --weight-{key}: {value};")
    space = theme.get("space")
    if is_object(space):
        for key, value in space.items():
            light_body.append(f"  --space-{key}: {value};")
    radius = theme.get("radius")
    if is_object(radius):
        for key, value in radius.items():
            light_body.append(f"  --radius-{key}: {value};")
    motion = theme.get("motion")
    if is_object(motion):
        for key, value in motion.items():
            light_body.append(f"  --motion-{key}: {value};")
    light_block = ":root {\n" + "\n".join(light_body) + "\n}"

    dark_body = color_lines(dark_color, "    ")
    dark_block = (
        "@media (prefers-color-scheme: dark) {\n  :root {\n"
        + "\n".join(dark_body)
        + "\n  }\n}"
    )
    return f"{light_block}\n{dark_block}"


def base_css(
    theme_id: str = "cast-default",
    config_dir: Path = CONFIG_DIR,
    template_dir: Path = TEMPLATE_DIR,
) -> str:
    root = compile_theme_root_css(load_theme(theme_id, config_dir))
    layout = load_template_module("styles.base.css", template_dir)
    return f"\n{root}\n{layout}"


def diagram_viewer_js(template_dir: Path = TEMPLATE_DIR) -> str:
    return load_template_module("interactions.diagram-viewer.js", template_dir)


def render_interaction_assets(
    specs: list[dict[str, Any]],
    ctx: RenderContext | None = None,
    template_dir: Path = TEMPLATE_DIR,
) -> tuple[str, str]:
    hooks: list[str] = []
    scripts: list[str] = []
    for spec in specs:
        iid = spec.get("id")
        if not isinstance(iid, str):
            continue
        hook_path = template_dir / f"hooks.{iid}.html"
        if hook_path.exists():
            hook = hook_path.read_text(encoding="utf-8")
            if ctx is not None and iid == "diagram-viewer":
                hook = hook.replace("Diagram viewer", attr(tr(ctx, "diagram.viewerAria", "Diagram viewer")))
                hook = hook.replace(">Close</button>", f">{render_i18n_text(ctx, 'diagram.close', 'Close')}</button>")
                hook = hook.replace('aria-label="Close"', f'aria-label="{attr(tr(ctx, "diagram.close", "Close"))}"')
            hooks.append(hook)
        if spec.get("requiresScript"):
            script_path = template_dir / f"interactions.{iid}.js"
            if script_path.exists():
                scripts.append(
                    f"<script data-renderer-owned=\"true\" data-interaction=\"{attr(iid)}\">{script_path.read_text(encoding='utf-8')}</script>"
                )
    return "".join(hooks), "".join(scripts)


def render_i18n_bootstrap(ctx: RenderContext) -> str:
    if len(ctx.locales) <= 1 and ctx.active_locale == "en":
        return ""
    payload = {
        "activeLocale": ctx.active_locale,
        "locales": ctx.locales,
        "strings": {
            locale: (ctx.i18n.get("locales", {}).get(locale, {}).get("strings", {}))
            for locale in ctx.locales
        },
    }
    source = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return f"<script data-renderer-owned=\"true\" data-interaction=\"i18n\">window.CAST_DOCS_I18N = {source};</script>"


def render_i18n_script(template_dir: Path = TEMPLATE_DIR) -> str:
    script_path = template_dir / "interactions.i18n.js"
    if not script_path.exists():
        return ""
    return (
        "<script data-renderer-owned=\"true\" data-interaction=\"i18n\">"
        f"{script_path.read_text(encoding='utf-8')}"
        "</script>"
    )


SHELL_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Z_]+)\s*\}\}")


def render_shell(template: str, slots: dict[str, str]) -> str:
    def lookup(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in slots:
            raise CastDocsError(f"shell template references unknown slot: {key}")
        return slots[key]
    return SHELL_PLACEHOLDER_RE.sub(lookup, template)


def render_html(
    doc: dict[str, Any],
    layout_id: str = "single-doc",
    config_dir: Path = CONFIG_DIR,
    template_dir: Path = TEMPLATE_DIR,
    profile: ProjectProfile | None = None,
) -> str:
    doc = apply_project_profile(doc, profile)
    metadata = doc["metadata"]
    i18n = load_config("i18n.json", config_dir)
    locales = document_locales(doc)
    active_locale = normalize_locale(metadata.get("language"), "en")
    if active_locale not in locales:
        locales.insert(0, active_locale)
    ctx = RenderContext(
        active_locale=active_locale,
        locales=locales,
        i18n=i18n,
        config_dir=config_dir,
        repo_root=profile.repo_root if profile else ROOT,
        metadata=metadata,
    )
    sections = as_list(doc.get("sections"))
    title_value = metadata.get("title", tr(ctx, "state.untitled", "Untitled"))
    title = localized_value(title_value, active_locale, "en")
    description = localized_value(metadata.get("description", ""), active_locale, "en")
    meta = metadata_line(metadata, ctx) if metadata.get("showMeta") is True else ""
    meta_html = f"<div class=\"doc-meta\">{meta}</div>" if meta else ""
    topbar_links = render_shell_links(metadata, "topbar", ctx)
    footer_links = render_footer_links(metadata, ctx)
    footer = footer_links or f"<a href=\"https://github.com/CAST-docs/cast-a-doc\" target=\"_blank\" rel=\"noopener noreferrer\">CAST Docs</a>"
    layout = load_layout(layout_id, config_dir)
    active_interactions = resolve_active_interactions(doc, layout, config_dir)
    lightbox, script = render_interaction_assets(active_interactions, ctx, template_dir)
    i18n_bootstrap = render_i18n_bootstrap(ctx)
    i18n_script = render_i18n_script(template_dir) if len(ctx.locales) > 1 or active_locale != "en" else ""

    shell_name = text(layout.get("shell")) or "single"
    shell = load_template_module(f"shell.{shell_name}.html", template_dir)
    doc_json = json.dumps(doc, indent=2, ensure_ascii=False).replace("</", "<\\/")
    slots = {
        "LANG": attr(metadata.get("language", "en")),
        "DESCRIPTION": attr(description or title),
        "TITLE": esc(title),
        "DISPLAY_TITLE": render_text(title_value, ctx),
        "TOPBAR_TITLE": render_topbar_title(metadata, title_value, ctx, profile),
        "LOGO": render_logo(metadata, ctx),
        "DOC_JSON": doc_json,
        "STYLE": base_css(config_dir=config_dir, template_dir=template_dir),
        "TOPBAR_LINKS": topbar_links,
        "LANGUAGE_SWITCHER": render_language_switcher(ctx),
        "DOC_META": meta_html,
        "SIDEBAR": render_sidebar([section for section in sections if is_object(section)], ctx),
        "SECTIONS": render_sections(sections, ctx),
        "PAGINATION": render_set_pagination(metadata, ctx),
        "FOOTER": footer,
        "INTERACTION_HOOKS": lightbox,
        "INTERACTION_SCRIPTS": f"{i18n_bootstrap}{script}{i18n_script}",
    }
    return render_shell(shell, slots)


class ProfileParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, list[tuple[str, str | None]]]] = []
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.srcs: list[str] = []
        self.doctype_seen = False
        self.unresolved = False

    def handle_decl(self, decl: str) -> None:
        if decl.lower().strip() == "doctype html":
            self.doctype_seen = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, attrs))
        for key, value in attrs:
            if key == "id" and value:
                self.ids.add(value)
            if key == "href" and value:
                self.hrefs.append(value)
            if key == "src" and value:
                self.srcs.append(value)
            if value and UNRESOLVED_RE.search(value):
                self.unresolved = True

    def handle_data(self, data: str) -> None:
        if UNRESOLVED_RE.search(data):
            self.unresolved = True


def validate_html_profile(html_text: str, profile: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    parser = ProfileParser()
    parser.feed(html_text)
    parser.close()

    if profile.get("doctypeRequired") and not parser.doctype_seen:
        errors.append("missing <!doctype html>")
    if parser.unresolved:
        errors.append("HTML contains unresolved template placeholders")

    allowed_tags = {tag.lower() for tag in set(profile["allowedTags"]["content"]) | set(profile["allowedTags"]["rendererOwned"])}
    forbidden_tags = {tag.lower() for tag in profile.get("forbiddenTags", [])}
    allowed_classes = set(profile.get("allowedClasses", []))
    global_attrs = {attribute.lower() for attribute in profile.get("globalAttributes", [])}
    tag_attrs = {
        key.lower(): {attribute.lower() for attribute in value}
        for key, value in profile.get("tagAttributes", {}).items()
    }
    forbidden_attrs = {attribute.lower() for attribute in profile.get("forbiddenAttributes", [])}
    allowed_schemes = set(profile.get("allowedSchemes", {}).get("userContent", [])) | set(profile.get("allowedSchemes", {}).get("rendererOwned", []))

    for tag, attrs in parser.tags:
        normalized_tag = tag.lower()
        attrs_map = {key.lower(): value for key, value in attrs}
        if normalized_tag in forbidden_tags:
            errors.append(f"forbidden tag: <{tag}>")
        if normalized_tag not in allowed_tags:
            errors.append(f"unsupported tag: <{tag}>")
        allowed_for_tag = global_attrs | tag_attrs.get(normalized_tag, set())
        for key, value in attrs:
            normalized_key = key.lower()
            if normalized_key in forbidden_attrs or normalized_key.startswith("on"):
                errors.append(f"forbidden attribute on <{tag}>: {key}")
            if normalized_key not in allowed_for_tag:
                errors.append(f"unsupported attribute on <{tag}>: {key}")
            if normalized_key == "class" and value:
                for cls in value.split():
                    if cls not in allowed_classes:
                        errors.append(f"unsupported class: {cls}")
            if normalized_key == "href" and value:
                kind = href_kind(value)
                if kind not in allowed_schemes:
                    errors.append(f"unsupported href scheme: {value}")
                if kind == "openinfinder" and attrs_map.get("data-interaction") != "finder-open":
                    errors.append("openinfinder hrefs must use data-interaction=\"finder-open\"")

    for href in parser.hrefs:
        if href.startswith("#") and href[1:] not in parser.ids:
            errors.append(f"anchor does not resolve: {href}")

    for src in parser.srcs:
        if media_src_kind(src) not in {"data-image", "relative", "http", "https"}:
            errors.append(f"unsupported image src scheme: {src}")

    if "<script src=" in html_text or "<link" in html_text:
        errors.append("external scripts or stylesheets are not allowed")

    return ValidationResult(sorted(set(errors)), warnings)


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
