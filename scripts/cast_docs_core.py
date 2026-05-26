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


def render_block(block: dict[str, Any]) -> str:
    renderers = {
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
        "source-refs": render_source_refs,
        "files": render_files,
        "action": render_action,
        "values-grid": render_values_grid,
        "acceptance-criteria": render_acceptance_criteria,
        "open-questions": render_open_questions,
    }
    renderer = renderers.get(block.get("type"))
    if not renderer:
        return f"<p class=\"section-empty\">Unsupported block: {esc(block.get('type'))}</p>"
    return renderer(block)


def document_has_block(doc: dict[str, Any], block_type: str) -> bool:
    found: set[str] = set()
    for section in as_list(doc.get("sections")):
        if is_object(section):
            collect_block_types(as_list(section.get("blocks")), found)
    return block_type in found


def render_toc(sections: list[dict[str, Any]]) -> str:
    items = []
    for index, section in enumerate(sections, start=1):
        number = f"{index:02d}"
        items.append(f"<li><a href=\"#{attr(section.get('id'))}\"><span>{number}</span>{esc(section.get('title'))}</a></li>")
    return f"<nav class=\"toc\" aria-label=\"Table of contents\"><ol>{''.join(items)}</ol></nav>"


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


def base_css() -> str:
    return """
:root {
  color-scheme: light dark;
  --bg: #f8f8f7;
  --surface: #ffffff;
  --soft: #f2f3f3;
  --text: #24272b;
  --muted: #68717b;
  --faint: #9aa1a8;
  --border: #dedede;
  --primary: #566f99;
  --primary-soft: #f1f3f6;
  --accent: #52686a;
  --info: #566f99;
  --info-soft: #f4f5f7;
  --warn: #8a6d3b;
  --warn-soft: #f8f4ea;
  --danger: #9b4d49;
  --danger-soft: #faf0ef;
  --ok: #55745f;
  --ok-soft: #eef4ef;
  --code: #f1f2f2;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
  --mono: "SFMono-Regular", "SF Mono", Consolas, "Liberation Mono", monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111315;
    --surface: #17191c;
    --soft: #202328;
    --text: #e2e5e8;
    --muted: #a1a7ad;
    --faint: #767d84;
    --border: #30343a;
    --primary: #9aaeca;
    --primary-soft: #1b2027;
    --accent: #9ab4b1;
    --info: #9aaeca;
    --info-soft: #1b2027;
    --warn: #c7b27e;
    --warn-soft: #242117;
    --danger: #d09a95;
    --danger-soft: #271b1a;
    --ok: #9ebaa5;
    --ok-soft: #1a241d;
    --code: #202328;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.7 var(--sans); -webkit-font-smoothing: antialiased; }
a { color: var(--primary); text-decoration: none; }
a:hover { text-decoration: underline; }
code, pre { font-family: var(--mono); }
code { background: var(--code); color: var(--accent); border: 1px solid var(--border); border-radius: 4px; padding: 1px 5px; font-size: .88em; }
pre { margin: 14px 0; padding: 14px 16px; overflow: auto; background: var(--code); border: 1px solid var(--border); border-radius: 8px; font-size: 12.5px; line-height: 1.55; }
.topbar { position: sticky; top: 0; z-index: 10; height: 52px; display: flex; align-items: center; gap: 18px; padding: 0 max(28px, calc((100vw - 960px) / 2)); background: color-mix(in srgb, var(--bg) 92%, transparent); backdrop-filter: blur(14px); border-bottom: 1px solid var(--border); }
.topbar-title { color: var(--text); font-weight: 600; }
.topbar-links { display: flex; gap: 12px; align-items: center; }
.topbar-links:empty { display: none; }
.topbar-link { color: var(--muted); font-size: 12.5px; }
.topbar-spacer { flex: 1; }
.doc { max-width: 960px; margin: 0 auto; padding: 52px 32px 84px; }
.doc-header { margin-bottom: 32px; padding-bottom: 26px; border-bottom: 1px solid var(--border); }
.doc-header h1 { margin: 0 0 10px; font-size: 34px; line-height: 1.18; letter-spacing: 0; }
.doc-meta { margin-top: 14px; color: var(--muted); font: 12.5px/1.4 var(--mono); }
.doc-summary, .toc, .callout, table, .details-block, .diagram, .participant-card, .value-card, .action-card { margin: 18px 0; }
.doc-summary, .toc, .details-block, .diagram, .participant-card, .value-card, .action-card { border: 1px solid var(--border); border-radius: 8px; background: var(--surface); }
.doc-summary { padding: 16px 18px; }
.doc-summary ul { margin: 0; }
.toc { padding: 16px 18px; }
.toc ol { margin: 0; padding-left: 22px; }
.toc span { display: inline-block; min-width: 34px; color: var(--muted); font-family: var(--mono); }
.doc-section { margin: 46px 0 0; scroll-margin-top: 70px; }
.doc-section h2 { margin: 0 0 16px; padding: 4px 0 5px 14px; border-left: 3px solid var(--primary); font-size: 22px; line-height: 1.25; }
.doc-section h3 { margin: 0 0 8px; font-size: 16px; }
.section-empty { color: var(--muted); font-style: italic; }
.callout { padding: 13px 16px; border: 1px solid var(--border); border-left: 3px solid var(--info); border-radius: 8px; background: var(--info-soft); }
.callout p { margin: 6px 0 0; }
.callout-info { border-left-color: var(--info); background: var(--info-soft); }
.callout-warning { border-left-color: var(--warn); background: var(--warn-soft); }
.callout-danger { border-left-color: var(--danger); background: var(--danger-soft); }
.callout-success { border-left-color: var(--ok); background: var(--ok-soft); }
table { width: 100%; border-collapse: collapse; overflow: hidden; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); font-size: 13.5px; }
th, td { padding: 11px 14px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
th { background: var(--soft); color: var(--muted); font-size: 12.5px; font-weight: 600; }
tr:last-child td { border-bottom: 0; }
.details-block { padding: 0 14px; }
.details-block summary { cursor: pointer; padding: 12px 0; font-weight: 700; }
.diagram { position: relative; padding: 16px; overflow: auto; }
.diagram figcaption { margin-bottom: 10px; color: var(--muted); font-size: 13px; font-weight: 700; }
.diagram svg { display: block; max-width: 100%; height: auto; margin: 0 auto; }
.diagram-toolbar { position: absolute; top: 10px; right: 10px; display: flex; gap: 6px; opacity: 0; transition: opacity .16s ease; }
.diagram:hover .diagram-toolbar { opacity: 1; }
button { border: 1px solid var(--border); border-radius: 5px; background: var(--surface); color: var(--text); cursor: pointer; font: 12px/1.2 var(--sans); padding: 5px 9px; }
.diff-block { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.diff-block > h3 { grid-column: 1 / -1; }
.diff-side { border: 1px solid var(--border); border-radius: 8px; background: var(--surface); overflow: hidden; }
.diff-side h3 { margin: 0; padding: 10px 12px; background: var(--soft); font-size: 14px; }
.diff-side pre { margin: 0; border: 0; border-radius: 0; }
.diff-side span { display: block; }
.line-add { color: var(--ok); }
.line-remove { color: var(--danger); }
.line-warning { color: var(--warn); }
.line-context { color: var(--text); }
.participants, .values-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }
.participant-card, .value-card, .action-card { padding: 14px 16px; }
.participant-card p, .value-card p, .action-card p { margin: 0; color: var(--muted); }
.source-refs, .files, .acceptance-criteria, .open-questions { padding-left: 22px; }
.prompt-block { margin-top: 10px; }
.doc-footer { margin-top: 56px; padding-top: 18px; border-top: 1px solid var(--border); color: var(--muted); font-size: 13px; text-align: center; }
.lightbox { position: fixed; inset: 0; z-index: 100; display: none; align-items: center; justify-content: center; padding: 32px; background: rgba(8, 13, 20, .82); }
.lightbox.open { display: flex; }
.lightbox-panel { position: relative; width: min(1120px, 96vw); height: min(760px, 88vh); border-radius: 10px; background: var(--surface); overflow: hidden; }
.lightbox-body { width: 100%; height: 100%; display: grid; place-items: center; overflow: hidden; cursor: grab; }
.lightbox-body svg { max-width: 92%; max-height: 82%; transform-origin: center; }
.lightbox-toolbar { position: absolute; left: 14px; bottom: 14px; display: flex; gap: 8px; }
.lightbox-close { position: absolute; top: 12px; right: 12px; z-index: 2; }
@media (max-width: 760px) {
  .topbar { padding: 12px 18px; height: auto; flex-wrap: wrap; }
  .doc { padding: 32px 20px 56px; }
  .doc-header h1 { font-size: 28px; }
  .diff-block { grid-template-columns: 1fr; }
}
@media print {
  .topbar, .diagram-toolbar, .lightbox { display: none !important; }
  .doc { max-width: none; padding: 0; }
}
"""


def diagram_viewer_js() -> str:
    return """
(() => {
  const lightbox = document.querySelector('.lightbox[data-interaction="diagram-viewer"]');
  if (!lightbox) return;
  const body = lightbox.querySelector('.lightbox-body');
  const toolbar = lightbox.querySelector('.lightbox-toolbar');
  const closeButton = lightbox.querySelector('.lightbox-close');
  let sourceSvg = null;
  let cloneSvg = null;
  let zoom = 1;
  let panX = 0;
  let panY = 0;
  function fileBase(svg) {
    return svg.closest('[data-download-name]')?.getAttribute('data-download-name') || 'diagram';
  }
  function serialize(svg) {
    const clone = svg.cloneNode(true);
    if (!clone.getAttribute('xmlns')) clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    return new XMLSerializer().serializeToString(clone);
  }
  function downloadBlob(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 250);
  }
  function downloadSvg(svg) {
    downloadBlob(new Blob([serialize(svg)], { type: 'image/svg+xml;charset=utf-8' }), `${fileBase(svg)}.svg`);
  }
  function downloadPng(svg) {
    const url = URL.createObjectURL(new Blob([serialize(svg)], { type: 'image/svg+xml;charset=utf-8' }));
    const img = new Image();
    img.onload = () => {
      const box = svg.viewBox && svg.viewBox.baseVal;
      const width = box && box.width ? box.width : 900;
      const height = box && box.height ? box.height : 520;
      const canvas = document.createElement('canvas');
      canvas.width = width * 2;
      canvas.height = height * 2;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.scale(2, 2);
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(url);
      canvas.toBlob((blob) => blob && downloadBlob(blob, `${fileBase(svg)}.png`), 'image/png');
    };
    img.src = url;
  }
  function setTransform() {
    if (cloneSvg) cloneSvg.style.transform = `translate(${panX}px, ${panY}px) scale(${zoom})`;
  }
  function makeButton(label, action) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    button.setAttribute('data-renderer-owned', 'true');
    button.addEventListener('click', action);
    return button;
  }
  function open(svg) {
    sourceSvg = svg;
    cloneSvg = svg.cloneNode(true);
    cloneSvg.removeAttribute('width');
    cloneSvg.removeAttribute('height');
    cloneSvg.style.transformOrigin = 'center';
    zoom = 1;
    panX = 0;
    panY = 0;
    body.replaceChildren(cloneSvg);
    toolbar.replaceChildren(
      makeButton('Zoom -', () => { zoom = Math.max(0.25, zoom * 0.8); setTransform(); }),
      makeButton('Zoom +', () => { zoom = Math.min(8, zoom * 1.25); setTransform(); }),
      makeButton('Reset', () => { zoom = 1; panX = 0; panY = 0; setTransform(); }),
      makeButton('SVG', () => downloadSvg(sourceSvg)),
      makeButton('PNG', () => downloadPng(sourceSvg))
    );
    lightbox.classList.add('open');
    setTransform();
  }
  function close() {
    lightbox.classList.remove('open');
    body.replaceChildren();
    toolbar.replaceChildren();
    sourceSvg = null;
    cloneSvg = null;
  }
  closeButton.addEventListener('click', close);
  lightbox.addEventListener('click', (event) => { if (event.target === lightbox) close(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') close(); });
  body.addEventListener('wheel', (event) => {
    if (!cloneSvg) return;
    event.preventDefault();
    zoom = Math.max(0.25, Math.min(8, zoom * Math.exp(-event.deltaY * 0.0015)));
    setTransform();
  }, { passive: false });
  let drag = null;
  body.addEventListener('mousedown', (event) => {
    if (!cloneSvg) return;
    drag = { x: event.clientX, y: event.clientY, panX, panY };
  });
  window.addEventListener('mousemove', (event) => {
    if (!drag) return;
    panX = drag.panX + event.clientX - drag.x;
    panY = drag.panY + event.clientY - drag.y;
    setTransform();
  });
  window.addEventListener('mouseup', () => { drag = null; });
  document.querySelectorAll('.diagram').forEach((figure) => {
    const svg = figure.querySelector('svg');
    if (!svg) return;
    const tools = document.createElement('div');
    tools.className = 'diagram-toolbar';
    tools.setAttribute('data-renderer-owned', 'true');
    tools.append(
      makeButton('Open', () => open(svg)),
      makeButton('SVG', () => downloadSvg(svg)),
      makeButton('PNG', () => downloadPng(svg))
    );
    figure.appendChild(tools);
  });
})();
"""


def render_html(doc: dict[str, Any]) -> str:
    metadata = doc["metadata"]
    sections = as_list(doc.get("sections"))
    title = metadata.get("title", "Untitled")
    description = metadata.get("description", "")
    meta = metadata_line(metadata)
    meta_html = f"<div class=\"doc-meta\">{meta}</div>" if meta else ""
    topbar_links = render_shell_links(metadata, "topbar")
    footer_links = render_footer_links(metadata)
    footer = footer_links or f"<a href=\"https://github.com/jinhuang712/cast-docs\" target=\"_blank\" rel=\"noopener noreferrer\">CAST Docs</a>"
    diagram_enabled = document_has_block(doc, "diagram")
    lightbox = ""
    script = ""
    if diagram_enabled:
        lightbox = (
            "<div class=\"lightbox\" data-renderer-owned=\"true\" data-interaction=\"diagram-viewer\" role=\"dialog\" aria-modal=\"true\" aria-label=\"Diagram viewer\">"
            "<div class=\"lightbox-panel\">"
            "<button class=\"lightbox-close\" type=\"button\" data-renderer-owned=\"true\" aria-label=\"Close\">Close</button>"
            "<div class=\"lightbox-body\"></div><div class=\"lightbox-toolbar\"></div></div></div>"
        )
        script = f"<script data-renderer-owned=\"true\" data-interaction=\"diagram-viewer\">{diagram_viewer_js()}</script>"

    return (
        "<!doctype html>\n"
        f"<html lang=\"{attr(metadata.get('language', 'en'))}\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<meta name=\"description\" content=\"{attr(description or title)}\">\n"
        f"<title>{esc(title)}</title>\n"
        f"<style>{base_css()}</style>\n"
        "</head>\n"
        "<body>\n"
        "<header class=\"topbar\">"
        f"<span class=\"topbar-title\">{esc(title)}</span>{topbar_links}<span class=\"topbar-spacer\"></span>"
        "</header>\n"
        "<article class=\"doc\">\n"
        f"<header class=\"doc-header\"><h1>{esc(title)}</h1>{meta_html}</header>\n"
        f"{render_toc([section for section in sections if is_object(section)])}\n"
        f"<main>{render_sections(sections)}</main>\n"
        f"<footer class=\"doc-footer\">{footer}</footer>\n"
        "</article>\n"
        f"{lightbox}\n"
        f"{script}\n"
        "</body>\n"
        "</html>\n"
    )


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
