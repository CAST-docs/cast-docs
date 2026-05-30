from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from cast_docs_common import ValidationResult, is_object
from cast_docs_common import RAW_DIAGRAM_LANGUAGES, looks_like_raw_diagram_source, normalized_code_language
from cast_docs_context import href_kind, media_src_kind


UNRESOLVED_RE = re.compile(r"\{\{\s*[A-Z_]+\s*\}\}")


class ProfileParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, list[tuple[str, str | None]]]] = []
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.srcs: list[str] = []
        self.raw_diagram_blocks: list[str] = []
        self._text_stack: list[dict[str, Any]] = []
        self.doctype_seen = False
        self.unresolved = False

    def handle_decl(self, decl: str) -> None:
        if decl.lower().strip() == "doctype html":
            self.doctype_seen = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, attrs))
        attrs_map = {key.lower(): value for key, value in attrs}
        for key, value in attrs:
            if key == "id" and value:
                self.ids.add(value)
            if key == "href" and value:
                self.hrefs.append(value)
            if key == "src" and value:
                self.srcs.append(value)
            if value and UNRESOLVED_RE.search(value):
                self.unresolved = True
        normalized_tag = tag.lower()
        if normalized_tag in {"pre", "code", "figcaption"}:
            self._text_stack.append({"tag": normalized_tag, "attrs": attrs_map, "text": []})

    def handle_data(self, data: str) -> None:
        if UNRESOLVED_RE.search(data):
            self.unresolved = True
        for frame in self._text_stack:
            frame["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag not in {"pre", "code", "figcaption"}:
            return
        for index in range(len(self._text_stack) - 1, -1, -1):
            frame = self._text_stack[index]
            if frame["tag"] != normalized_tag:
                continue
            content = "".join(frame["text"])
            attrs = frame["attrs"]
            language = normalized_code_language(attrs.get("data-language"))
            if (
                language in RAW_DIAGRAM_LANGUAGES
                or looks_like_raw_diagram_source(content)
                or (normalized_tag == "figcaption" and content.strip().lower() in {"mermaid source", "flowchart source", "diagram source"})
            ):
                self.raw_diagram_blocks.append(normalized_tag)
            del self._text_stack[index:]
            return


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
    if parser.raw_diagram_blocks:
        errors.append("HTML contains raw diagram source; diagrams must render as SVG figures")
    style_position = html_text.find("<style>")
    body_position = html_text.find("<body>")
    if style_position == -1:
        errors.append("missing inline <style> block")
    elif body_position != -1 and style_position > body_position:
        errors.append("inline <style> must appear before <body> to avoid unstyled first paint")

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
