from __future__ import annotations

import html
import re
from typing import Any
from xml.etree import ElementTree as ET

from cast_docs_common import attr


HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
SVG_PATH_RE = re.compile(r"^[MmZzLlHhVvCcSsQqTtAa0-9,.\s+-]+$")
SVG_POINTS_RE = re.compile(r"^[0-9,.\s+-]+$")
SVG_NUMBER_RE = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)$")
SVG_LENGTH_VALUE_RE = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:px|rem|em|%)?$")
SVG_DASHARRAY_RE = re.compile(r"^(?:none|[0-9,.\s+-]+)$")
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
SVG_ALLOWED_TAGS = {
    "svg",
    "g",
    "path",
    "rect",
    "circle",
    "ellipse",
    "line",
    "polyline",
    "polygon",
    "text",
    "tspan",
    "title",
    "desc",
}
SVG_TEXT_TAGS = {"text", "tspan", "title", "desc"}
SVG_ALLOWED_ATTRS = {
    "svg": {"viewBox", "width", "height", "role", "aria-label", "fill", "stroke", "xmlns"},
    "g": {"fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "opacity", "transform"},
    "path": {"d", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "opacity", "fill-opacity", "stroke-opacity", "transform"},
    "rect": {"x", "y", "width", "height", "rx", "ry", "fill", "stroke", "stroke-width", "opacity", "fill-opacity", "stroke-opacity", "transform"},
    "circle": {"cx", "cy", "r", "fill", "stroke", "stroke-width", "opacity", "fill-opacity", "stroke-opacity", "transform"},
    "ellipse": {"cx", "cy", "rx", "ry", "fill", "stroke", "stroke-width", "opacity", "fill-opacity", "stroke-opacity", "transform"},
    "line": {"x1", "y1", "x2", "y2", "stroke", "stroke-width", "stroke-linecap", "stroke-dasharray", "opacity", "transform"},
    "polyline": {"points", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "opacity", "transform"},
    "polygon": {"points", "fill", "stroke", "stroke-width", "stroke-linejoin", "stroke-dasharray", "opacity", "fill-opacity", "stroke-opacity", "transform"},
    "text": {"x", "y", "dx", "dy", "fill", "font-size", "text-anchor", "dominant-baseline", "opacity", "transform"},
    "tspan": {"x", "y", "dx", "dy", "fill", "font-size", "text-anchor", "dominant-baseline", "opacity"},
    "title": set(),
    "desc": set(),
}
SVG_TOKEN_ATTRS = {"fill", "stroke"}
SVG_LENGTH_ATTRS = {
    "x",
    "y",
    "x1",
    "y1",
    "x2",
    "y2",
    "cx",
    "cy",
    "r",
    "rx",
    "ry",
    "width",
    "height",
    "dx",
    "dy",
    "stroke-width",
    "font-size",
}
SVG_NUMBER_ATTRS = {"opacity", "fill-opacity", "stroke-opacity"}


def svg_local_name(name: str) -> str:
    if name.startswith("{"):
        return name.rsplit("}", 1)[-1]
    return name


def svg_tag_name(name: str) -> str | None:
    if name.startswith("{"):
        namespace, local = name[1:].split("}", 1)
        return local if namespace == SVG_NAMESPACE else None
    return name


def svg_attr_name(name: str) -> str | None:
    if name.startswith("{"):
        namespace, local = name[1:].split("}", 1)
        if namespace == "http://www.w3.org/XML/1998/namespace" and local in {"lang", "space"}:
            return f"xml:{local}"
        return None
    return name


def validate_svg_attr_value(name: str, value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if name in SVG_TOKEN_ATTRS:
        return stripped == "none" or stripped == "currentColor" or HEX_COLOR_RE.match(stripped) is not None
    if name in SVG_LENGTH_ATTRS:
        return SVG_LENGTH_VALUE_RE.match(stripped) is not None
    if name in SVG_NUMBER_ATTRS:
        return SVG_NUMBER_RE.match(stripped) is not None
    if name == "viewBox":
        parts = stripped.replace(",", " ").split()
        return len(parts) == 4 and all(SVG_NUMBER_RE.match(part) for part in parts)
    if name == "d":
        return SVG_PATH_RE.match(stripped) is not None
    if name == "points":
        return SVG_POINTS_RE.match(stripped) is not None
    if name == "stroke-dasharray":
        return SVG_DASHARRAY_RE.match(stripped) is not None
    if name in {"stroke-linecap", "stroke-linejoin"}:
        return stripped in {"butt", "round", "square", "miter", "bevel"}
    if name == "text-anchor":
        return stripped in {"start", "middle", "end"}
    if name == "dominant-baseline":
        return stripped in {"auto", "middle", "central", "hanging", "text-before-edge", "text-after-edge"}
    if name == "role":
        return stripped == "img"
    if name == "aria-label":
        return "<" not in stripped and ">" not in stripped
    if name == "xmlns":
        return stripped == SVG_NAMESPACE
    if name == "transform":
        if any(token in stripped.lower() for token in ("url", "matrix3d")):
            return False
        return re.match(r"^[a-zA-Z0-9(),.\s+-]+$", stripped) is not None
    return False


def sanitize_svg_element(element: ET.Element, errors: list[str], path: str) -> str:
    tag = svg_tag_name(element.tag)
    if tag is None:
        errors.append(f"{path}: SVG element namespace is not allowed")
        return ""
    if tag not in SVG_ALLOWED_TAGS:
        errors.append(f"{path}: SVG tag <{tag}> is not allowed")
        return ""

    attrs: list[str] = []
    allowed_attrs = SVG_ALLOWED_ATTRS[tag]
    if tag == "svg":
        attrs.append(f'xmlns="{SVG_NAMESPACE}"')
    for raw_name, value in sorted(element.attrib.items()):
        name = svg_attr_name(raw_name)
        if name is None:
            errors.append(f"{path}: SVG namespaced attribute {raw_name} is not allowed")
            continue
        lower_name = name.lower()
        if lower_name.startswith("on") or lower_name in {"href", "xlink:href", "style", "class", "id"}:
            errors.append(f"{path}: SVG attribute {name} is not allowed")
            continue
        if name not in allowed_attrs:
            errors.append(f"{path}: SVG attribute {name} is not allowed on <{tag}>")
            continue
        if name == "xmlns" and tag == "svg":
            continue
        if not validate_svg_attr_value(name, value):
            errors.append(f"{path}: SVG attribute {name} has an unsupported value")
            continue
        attrs.append(f'{name}="{attr(value.strip())}"')

    children: list[str] = []
    if element.text and element.text.strip():
        if tag not in SVG_TEXT_TAGS:
            errors.append(f"{path}: SVG text is not allowed inside <{tag}>")
        else:
            children.append(html.escape(element.text.strip(), quote=False))
    for child in list(element):
        children.append(sanitize_svg_element(child, errors, f"{path}.{svg_local_name(child.tag)}"))
        if child.tail and child.tail.strip():
            if tag not in SVG_TEXT_TAGS:
                errors.append(f"{path}: SVG text tail is not allowed inside <{tag}>")
            else:
                children.append(html.escape(child.tail.strip(), quote=False))

    attr_text = f" {' '.join(attrs)}" if attrs else ""
    return f"<{tag}{attr_text}>{''.join(children)}</{tag}>"


def sanitize_svg(svg_text: str, path: str = "svg") -> tuple[str | None, list[str]]:
    errors: list[str] = []
    lowered = svg_text.lower()
    if any(token in lowered for token in ("<!doctype", "<!entity", "<?xml-stylesheet", "<?")):
        return None, [f"{path}: SVG declarations and processing instructions are not allowed"]
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        return None, [f"{path}: SVG is not well-formed XML: {exc}"]
    if svg_tag_name(root.tag) != "svg":
        return None, [f"{path}: SVG root must be <svg>"]
    sanitized = sanitize_svg_element(root, errors, path)
    return (None if errors else sanitized), errors
