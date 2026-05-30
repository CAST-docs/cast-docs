from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from cast_docs_common import (
    CONFIG_DIR,
    RAW_DIAGRAM_LANGUAGES,
    SUPPORTED_LOCALES,
    ValidationResult,
    as_list,
    is_localized_object,
    is_object,
    load_config,
    looks_like_raw_diagram_source,
    normalized_code_language,
)
from cast_docs_context import href_kind, media_src_kind
from cast_docs_inline import INLINE_LINK_SCHEMES, INLINE_MARK_CATEGORIES
from cast_docs_svg import sanitize_svg


SECTION_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SAFE_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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
        elif (
            normalized_code_language(block.get("language")) in RAW_DIAGRAM_LANGUAGES
            or looks_like_raw_diagram_source(block.get("code"))
        ):
            errors.append(f"{path} contains raw diagram source; use a diagram block that renders to SVG")
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
                else:
                    _, svg_errors = sanitize_svg(content, f"{path}.source.content")
                    errors.extend(svg_errors)
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
    if metadata.get("breadcrumbTitle") is not None:
        validate_localized_string(metadata.get("breadcrumbTitle"), "metadata.breadcrumbTitle", errors, non_empty=True)
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
