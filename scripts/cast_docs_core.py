#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
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
UNRESOLVED_RE = re.compile(r"\{\{\s*[^}]+\s*\}\}")


class CastDocsError(Exception):
    pass


@dataclass
class ValidationResult:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CastDocsError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def load_config(name: str, config_dir: Path = CONFIG_DIR) -> Any:
    return load_json(config_dir / name)


def load_template_module(name: str, template_dir: Path = TEMPLATE_DIR) -> str:
    path = template_dir / name
    if not path.exists():
        raise CastDocsError(f"template module not found: {path}")
    return path.read_text(encoding="utf-8")


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
        if not isinstance(label, str) or not label.strip():
            errors.append(f"{path}.label must be a non-empty string")
        if not isinstance(href, str) or not href.strip():
            errors.append(f"{path}.href must be a non-empty string")
        elif href_kind(href) not in {"anchor", "relative", "http", "https"}:
            errors.append(f"{path}.href uses an unsupported URL scheme")
        if placement not in {"topbar", "footer"}:
            errors.append(f"{path}.placement must be topbar or footer")


def collect_block_types(blocks: list[Any], found: set[str]) -> None:
    for block in blocks:
        if not is_object(block):
            continue
        block_type = block.get("type")
        if isinstance(block_type, str):
            found.add(block_type)
        collect_block_types(as_list(block.get("blocks")), found)


def validate_block(block: Any, path: str, errors: list[str]) -> None:
    if not is_object(block):
        errors.append(f"{path} must be an object")
        return
    block_type = block.get("type")
    if not isinstance(block_type, str):
        errors.append(f"{path}.type must be a string")
        return

    def require_string(key: str) -> None:
        if not isinstance(block.get(key), str) or not block.get(key):
            errors.append(f"{path}.{key} must be a non-empty string")

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
            if not isinstance(item.get("label"), str) or not item.get("label"):
                errors.append(f"{path}.items[{index}].label must be a non-empty string")
            if not isinstance(item.get("body"), str):
                errors.append(f"{path}.items[{index}].body must be a string")
    elif block_type == "paragraph":
        if not isinstance(block.get("text"), str):
            errors.append(f"{path}.text must be a string")
    elif block_type == "list":
        for index, item in enumerate(require_array("items")):
            if not isinstance(item, str):
                errors.append(f"{path}.items[{index}] must be a string")
    elif block_type == "callout":
        if block.get("variant") not in {"info", "warning", "danger", "success"}:
            errors.append(f"{path}.variant must be one of info, warning, danger, success")
        if not isinstance(block.get("body"), str):
            errors.append(f"{path}.body must be a string")
    elif block_type == "table":
        headers = require_array("headers")
        rows = require_array("rows")
        for index, header in enumerate(headers):
            if not isinstance(header, str):
                errors.append(f"{path}.headers[{index}] must be a string")
        for row_index, row in enumerate(rows):
            if not isinstance(row, list):
                errors.append(f"{path}.rows[{row_index}] must be an array")
                continue
            if headers and len(row) != len(headers):
                errors.append(f"{path}.rows[{row_index}] must have {len(headers)} cells")
            for cell_index, cell in enumerate(row):
                if not isinstance(cell, str):
                    errors.append(f"{path}.rows[{row_index}][{cell_index}] must be a string")
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
                        if not isinstance(step.get(key), str) or not step.get(key):
                            errors.append(f"{path}.source.steps[{index}].{key} must be a non-empty string")
            elif fmt == "structured-flow":
                for index, node in enumerate(as_list(source.get("nodes"))):
                    if not is_object(node) or not isinstance(node.get("id"), str) or not isinstance(node.get("label"), str):
                        errors.append(f"{path}.source.nodes[{index}] must include string id and label")
                for index, edge in enumerate(as_list(source.get("edges"))):
                    if not is_object(edge) or not isinstance(edge.get("from"), str) or not isinstance(edge.get("to"), str):
                        errors.append(f"{path}.source.edges[{index}] must include string from and to")
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
    elif block_type == "diff":
        for side_key in ("left", "right"):
            side = block.get(side_key)
            if not is_object(side):
                errors.append(f"{path}.{side_key} must be an object")
                continue
            if not isinstance(side.get("label"), str) or not side.get("label"):
                errors.append(f"{path}.{side_key}.label must be a non-empty string")
            for index, line in enumerate(as_list(side.get("lines"))):
                if not is_object(line):
                    errors.append(f"{path}.{side_key}.lines[{index}] must be an object")
                    continue
                if line.get("kind") not in {"add", "remove", "warning", "context"}:
                    errors.append(f"{path}.{side_key}.lines[{index}].kind is unsupported")
                if not isinstance(line.get("text"), str):
                    errors.append(f"{path}.{side_key}.lines[{index}].text must be a string")
    elif block_type == "participants":
        for index, item in enumerate(require_array("items")):
            if not is_object(item) or not isinstance(item.get("name"), str) or not isinstance(item.get("responsibility"), str):
                errors.append(f"{path}.items[{index}] must include name and responsibility")
    elif block_type == "source-refs":
        for index, item in enumerate(require_array("items")):
            if not is_object(item) or not isinstance(item.get("label"), str) or not isinstance(item.get("url"), str):
                errors.append(f"{path}.items[{index}] must include label and url")
                continue
            if href_kind(item["url"]) not in {"anchor", "relative", "http", "https"}:
                errors.append(f"{path}.items[{index}].url uses an unsupported URL scheme")
    elif block_type == "files":
        for index, item in enumerate(require_array("items")):
            if not is_object(item) or not isinstance(item.get("path"), str):
                errors.append(f"{path}.items[{index}] must include path")
    elif block_type == "action":
        require_string("title")
        require_string("description")
        if block.get("priority", "none") not in {"p0", "p1", "p2", "none"}:
            errors.append(f"{path}.priority is unsupported")
    elif block_type == "values-grid":
        for index, item in enumerate(require_array("items")):
            if not is_object(item) or not isinstance(item.get("title"), str) or not isinstance(item.get("body"), str):
                errors.append(f"{path}.items[{index}] must include title and body")
    elif block_type == "acceptance-criteria":
        for index, item in enumerate(require_array("items")):
            if not isinstance(item, str):
                errors.append(f"{path}.items[{index}] must be a string")
    elif block_type == "open-questions":
        for index, item in enumerate(require_array("questions")):
            if not isinstance(item, str):
                errors.append(f"{path}.questions[{index}] must be a string")
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
        errors.append("metadata.title must be a non-empty string")
    if metadata.get("language") not in {"zh-CN", "en"}:
        errors.append("metadata.language must be zh-CN or en")
    validate_shell_links(metadata, errors)

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
        if not isinstance(section.get("title"), str) or not section.get("title"):
            errors.append(f"{path}.title must be a non-empty string")
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


def metadata_line(metadata: dict[str, Any]) -> str:
    parts: list[str] = []
    owner = metadata.get("owner")
    updated_at = metadata.get("updatedAt")
    if isinstance(owner, str) and owner and owner != "unknown":
        parts.append(f"Owner {esc(owner)}")
    if isinstance(updated_at, str) and updated_at:
        parts.append(f"Updated {esc(updated_at)}")
    return " · ".join(parts)


def render_summary_block(block: dict[str, Any]) -> str:
    items = []
    for item in as_list(block.get("items")):
        if is_object(item):
            items.append(f"<li><strong>{esc(item.get('label'))}:</strong> {esc(item.get('body'))}</li>")
    return f"<section class=\"doc-summary\" data-component=\"summary-block\"><ul>{''.join(items)}</ul></section>"


def render_paragraph(block: dict[str, Any]) -> str:
    return f"<p>{esc(block.get('text'))}</p>"


def render_list(block: dict[str, Any]) -> str:
    tag = "ol" if block.get("ordered") else "ul"
    items = "".join(f"<li>{esc(item)}</li>" for item in as_list(block.get("items")))
    return f"<{tag}>{items}</{tag}>"


def render_callout(block: dict[str, Any]) -> str:
    variant = block.get("variant", "info")
    cls = {
        "info": "callout callout-info",
        "warning": "callout callout-warning",
        "danger": "callout callout-danger",
        "success": "callout callout-success",
    }.get(variant, "callout callout-info")
    title = block.get("title")
    title_html = f"<strong>{esc(title)}</strong>" if title else ""
    return (
        f"<aside class=\"{cls}\" data-component=\"callout\">"
        f"{title_html}<p>{esc(block.get('body'))}</p>"
        "</aside>"
    )


def render_table(block: dict[str, Any]) -> str:
    table_type = block.get("tableType", "data")
    cls = {
        "risk": "risk-table",
        "decision": "decision-table",
        "data": "data-table",
    }.get(table_type, "data-table")
    headers = "".join(f"<th scope=\"col\">{esc(header)}</th>" for header in as_list(block.get("headers")))
    rows = []
    for row in as_list(block.get("rows")):
        if isinstance(row, list):
            rows.append("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>")
    return f"<table class=\"{cls}\" data-component=\"table\" data-table-type=\"{attr(table_type)}\"><thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def render_details(block: dict[str, Any]) -> str:
    open_attr = " open" if block.get("open") else ""
    body = "".join(render_block(child) for child in as_list(block.get("blocks")) if is_object(child))
    return f"<details class=\"details-block\" data-component=\"details-block\"{open_attr}><summary>{esc(block.get('summary'))}</summary>{body}</details>"


def render_code(block: dict[str, Any]) -> str:
    language = block.get("language", "")
    lang_attr = f" data-language=\"{attr(language)}\"" if language else ""
    return f"<pre class=\"code-block\" data-component=\"code-block\"{lang_attr}><code{lang_attr}>{esc(block.get('code'))}</code></pre>"


def svg_text(value: Any) -> str:
    return html.escape(text(value), quote=False)


def render_sequence_svg(block: dict[str, Any]) -> str:
    steps = as_list(block.get("source", {}).get("steps"))
    width = 860
    row_height = 68
    height = max(160, 58 + row_height * len(steps))
    rows = []
    for index, step in enumerate(steps):
        y = 36 + index * row_height
        rows.append(
            f"<rect x=\"32\" y=\"{y}\" width=\"796\" height=\"42\" rx=\"7\" fill=\"#f3f4f4\" stroke=\"#9aa1a8\" stroke-width=\"1\"/>"
            f"<text x=\"58\" y=\"{y + 26}\" fill=\"#2f3439\" font-size=\"14\">{svg_text(step.get('from'))} -> {svg_text(step.get('to'))}</text>"
            f"<text x=\"430\" y=\"{y + 26}\" fill=\"#68717b\" font-size=\"13\" text-anchor=\"middle\">{svg_text(step.get('label'))}</text>"
        )
    return f"<svg viewBox=\"0 0 {width} {height}\" xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-label=\"{attr(block.get('title') or 'Sequence diagram')}\">{''.join(rows)}</svg>"


def render_flow_svg(block: dict[str, Any]) -> str:
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
            parts.append(f"<text x=\"{(x1 + x2) / 2:.0f}\" y=\"66\" text-anchor=\"middle\" font-size=\"12\" fill=\"#68717b\">{svg_text(edge.get('label'))}</text>")
    for index, node in enumerate(nodes):
        if not is_object(node):
            continue
        x = 80 + index * 220
        parts.append(f"<rect x=\"{x}\" y=\"54\" width=\"120\" height=\"56\" rx=\"7\" fill=\"#f3f4f4\" stroke=\"#9aa1a8\"></rect>")
        parts.append(f"<text x=\"{x + 60}\" y=\"87\" text-anchor=\"middle\" font-size=\"13\" fill=\"#2f3439\">{svg_text(node.get('label'))}</text>")
    return f"<svg viewBox=\"0 0 {width} {height}\" xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-label=\"{attr(block.get('title') or 'Flow diagram')}\">{''.join(parts)}</svg>"


def render_diagram(block: dict[str, Any]) -> str:
    source = block.get("source", {})
    fmt = source.get("format")
    if fmt == "structured-sequence":
        svg = render_sequence_svg(block)
    elif fmt == "structured-flow":
        svg = render_flow_svg(block)
    elif fmt == "svg":
        svg = text(source.get("content"))
    else:
        svg = "<svg viewBox=\"0 0 320 100\" xmlns=\"http://www.w3.org/2000/svg\"><text x=\"20\" y=\"50\">Unsupported diagram</text></svg>"
    name = attr(block.get("downloadName") or "diagram")
    title = block.get("title")
    caption = f"<figcaption>{esc(title)}</figcaption>" if title else ""
    return f"<figure class=\"diagram\" data-component=\"diagram\" data-download-name=\"{name}\">{caption}{svg}</figure>"


def render_diff(block: dict[str, Any]) -> str:
    def side_html(side: dict[str, Any]) -> str:
        lines = []
        for line in as_list(side.get("lines")):
            if is_object(line):
                kind = line.get("kind", "context")
                lines.append(f"<span class=\"line-{attr(kind)}\">{esc(line.get('text'))}</span>")
        return f"<div class=\"diff-side\"><h3>{esc(side.get('label'))}</h3><pre><code>{chr(10).join(lines)}</code></pre></div>"

    left = side_html(block.get("left", {}))
    right = side_html(block.get("right", {}))
    title = f"<h3>{esc(block.get('title'))}</h3>" if block.get("title") else ""
    return f"<section class=\"diff-block\" data-component=\"diff-block\">{title}{left}{right}</section>"


def render_participants(block: dict[str, Any]) -> str:
    cards = []
    for item in as_list(block.get("items")):
        if not is_object(item):
            continue
        role = f"<p><em>{esc(item.get('role'))}</em></p>" if item.get("role") else ""
        cards.append(f"<div class=\"participant-card\"><h3>{esc(item.get('name'))}</h3>{role}<p>{esc(item.get('responsibility'))}</p></div>")
    return f"<section class=\"participants\" data-component=\"participants\">{''.join(cards)}</section>"


def render_source_refs(block: dict[str, Any]) -> str:
    items = []
    for item in as_list(block.get("items")):
        if not is_object(item):
            continue
        href = attr(item.get("url"))
        label = esc(item.get("label"))
        note = f" — {esc(item.get('text'))}" if item.get("text") else ""
        target = " target=\"_blank\" rel=\"noopener noreferrer\"" if href.startswith(("http://", "https://")) else ""
        items.append(f"<li><a href=\"{href}\"{target}>{label}</a>{note}</li>")
    return f"<ul class=\"source-refs\" data-component=\"source-refs\">{''.join(items)}</ul>"


def render_files(block: dict[str, Any]) -> str:
    items = []
    for item in as_list(block.get("items")):
        if not is_object(item):
            continue
        path = esc(item.get("path"))
        line = f":{esc(item.get('lineStart'))}" if item.get("lineStart") else ""
        note = f" — {esc(item.get('note'))}" if item.get("note") else ""
        if item.get("url"):
            items.append(f"<li><a href=\"{attr(item.get('url'))}\">{path}{line}</a>{note}</li>")
        else:
            items.append(f"<li><code>{path}{line}</code>{note}</li>")
    return f"<ul class=\"files\" data-component=\"files\">{''.join(items)}</ul>"


def render_action(block: dict[str, Any]) -> str:
    prompt = f"<pre class=\"prompt-block\"><code>{esc(block.get('prompt'))}</code></pre>" if block.get("prompt") else ""
    return f"<section class=\"action-card\" data-component=\"action-card\"><h3>{esc(block.get('title'))}</h3><p>{esc(block.get('description'))}</p>{prompt}</section>"


def render_values_grid(block: dict[str, Any]) -> str:
    cards = []
    for item in as_list(block.get("items")):
        if is_object(item):
            cards.append(f"<div class=\"value-card\"><h3>{esc(item.get('title'))}</h3><p>{esc(item.get('body'))}</p></div>")
    return f"<section class=\"values-grid\" data-component=\"values-grid\">{''.join(cards)}</section>"


def render_acceptance_criteria(block: dict[str, Any]) -> str:
    items = "".join(f"<li>{esc(item)}</li>" for item in as_list(block.get("items")))
    return f"<ol class=\"acceptance-criteria\" data-component=\"acceptance-criteria\">{items}</ol>"


def render_open_questions(block: dict[str, Any]) -> str:
    items = "".join(f"<li>{esc(item)}</li>" for item in as_list(block.get("questions")))
    return f"<ul class=\"open-questions\" data-component=\"open-questions\">{items}</ul>"


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


def render_block(block: dict[str, Any]) -> str:
    renderers = build_block_type_renderer_map()
    renderer = renderers.get(block.get("type"))
    if not renderer:
        return f"<p class=\"section-empty\">Unsupported block: {esc(block.get('type'))}</p>"
    return renderer(block)


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


def render_toc(sections: list[dict[str, Any]]) -> str:
    items = []
    for index, section in enumerate(sections, start=1):
        number = f"{index:02d}"
        items.append(f"<li><a href=\"#{attr(section.get('id'))}\"><span>{number}</span>{esc(section.get('title'))}</a></li>")
    return f"<nav class=\"toc\" aria-label=\"Table of contents\"><ol>{''.join(items)}</ol></nav>"


def render_sidebar(sections: list[dict[str, Any]]) -> str:
    toc = render_toc(sections)
    return f"<p class=\"nav-title\">Contents</p>{toc}"


def render_shell_links(metadata: dict[str, Any], placement: str) -> str:
    links = []
    for item in as_list(metadata.get("shellLinks")):
        if not is_object(item) or item.get("placement", "topbar") != placement:
            continue
        href = text(item.get("href"))
        target = " target=\"_blank\" rel=\"noopener noreferrer\"" if href.startswith(("http://", "https://")) else ""
        links.append(f"<a class=\"topbar-link\" href=\"{attr(href)}\"{target}>{esc(item.get('label'))}</a>")
    if not links:
        return ""
    return f"<nav class=\"topbar-links\" data-slot=\"topbar-links\" aria-label=\"Document links\">{''.join(links)}</nav>"


def render_footer_links(metadata: dict[str, Any]) -> str:
    links = []
    for item in as_list(metadata.get("shellLinks")):
        if not is_object(item) or item.get("placement") != "footer":
            continue
        href = text(item.get("href"))
        target = " target=\"_blank\" rel=\"noopener noreferrer\"" if href.startswith(("http://", "https://")) else ""
        links.append(f"<a href=\"{attr(href)}\"{target}>{esc(item.get('label'))}</a>")
    return " · ".join(links)


def render_sections(sections: list[Any]) -> str:
    rendered = []
    for section in sections:
        if not is_object(section):
            continue
        blocks = "".join(render_block(block) for block in as_list(section.get("blocks")) if is_object(block))
        if not blocks:
            blocks = "<p class=\"section-empty\">No content.</p>"
        rendered.append(
            f"<section class=\"doc-section\" data-component=\"section\" id=\"{attr(section.get('id'))}\">"
            f"<h2>{esc(section.get('title'))}</h2>{blocks}</section>"
        )
    return "".join(rendered)


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
            hooks.append(hook_path.read_text(encoding="utf-8"))
        if spec.get("requiresScript"):
            script_path = template_dir / f"interactions.{iid}.js"
            if script_path.exists():
                scripts.append(
                    f"<script data-renderer-owned=\"true\" data-interaction=\"{attr(iid)}\">{script_path.read_text(encoding='utf-8')}</script>"
                )
    return "".join(hooks), "".join(scripts)


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
) -> str:
    metadata = doc["metadata"]
    sections = as_list(doc.get("sections"))
    title = metadata.get("title", "Untitled")
    description = metadata.get("description", "")
    meta = metadata_line(metadata)
    meta_html = f"<div class=\"doc-meta\">{meta}</div>" if meta else ""
    topbar_links = render_shell_links(metadata, "topbar")
    footer_links = render_footer_links(metadata)
    footer = footer_links or f"<a href=\"https://github.com/CAST-docs/cast-docs\" target=\"_blank\" rel=\"noopener noreferrer\">CAST Docs</a>"
    layout = load_layout(layout_id, config_dir)
    active_interactions = resolve_active_interactions(doc, layout, config_dir)
    lightbox, script = render_interaction_assets(active_interactions, template_dir)

    shell_name = text(layout.get("shell")) or "single"
    shell = load_template_module(f"shell.{shell_name}.html", template_dir)
    slots = {
        "LANG": attr(metadata.get("language", "en")),
        "DESCRIPTION": attr(description or title),
        "TITLE": esc(title),
        "STYLE": base_css(config_dir=config_dir, template_dir=template_dir),
        "TOPBAR_LINKS": topbar_links,
        "DOC_META": meta_html,
        "SIDEBAR": render_sidebar([section for section in sections if is_object(section)]),
        "SECTIONS": render_sections(sections),
        "FOOTER": footer,
        "INTERACTION_HOOKS": lightbox,
        "INTERACTION_SCRIPTS": script,
    }
    return render_shell(shell, slots)


class ProfileParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, list[tuple[str, str | None]]]] = []
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
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
