#!/usr/bin/env python3
from __future__ import annotations

import argparse
import colorsys
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


HEX_COLOR_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RULE_RE = re.compile(r"([^{}]+)\{([^{}]+)\}", re.MULTILINE)
BADGE_SELECTOR_RE = re.compile(r"\.(?:status-pill|topbar-pill|open-question-marker)\b")
LARGE_AREA_RE = re.compile(r"\b(?:body|\.doc|\.topbar|\.sidebar|\.doc-header|\.doc-section|\.set-index)\b")
VIEWPORT_FONT_RE = re.compile(r"font(?:-size)?\s*:[^;]*(?:vw|vh|vmin|vmax)")
RAW_TRANSITION_RE = re.compile(r"\btransition(?:-[a-z-]+)?\s*:[^;]*(?:\d+(?:\.\d+)?m?s)")


class StyleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.in_style = False
        self.styles: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "style":
            self.in_style = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style":
            self.in_style = False

    def handle_data(self, data: str) -> None:
        if self.in_style:
            self.styles.append(data)


def expand_hex(value: str) -> str:
    if len(value) == 3:
        return "".join(ch * 2 for ch in value)
    return value


def saturation(hex_color: str) -> float:
    value = expand_hex(hex_color)
    red = int(value[0:2], 16) / 255
    green = int(value[2:4], 16) / 255
    blue = int(value[4:6], 16) / 255
    _, _, sat = colorsys.rgb_to_hls(red, green, blue)
    return sat


def lint_css(css: str, path: Path) -> list[str]:
    errors: list[str] = []
    for selector, body in RULE_RE.findall(css):
        selector = " ".join(selector.split())
        declarations = {part.split(":", 1)[0].strip(): part.split(":", 1)[1].strip() for part in body.split(";") if ":" in part}

        if VIEWPORT_FONT_RE.search(body):
            errors.append(f"{path}: {selector}: font sizing must not use viewport units")
        letter_spacing = declarations.get("letter-spacing")
        if letter_spacing and letter_spacing.strip().startswith("-"):
            errors.append(f"{path}: {selector}: letter-spacing must not be negative")
        if RAW_TRANSITION_RE.search(body) and "var(--motion-" not in body:
            errors.append(f"{path}: {selector}: transition durations should use motion tokens")

        for color in HEX_COLOR_RE.findall(body):
            sat = saturation(color)
            if sat > 0.72:
                errors.append(f"{path}: {selector}: color #{color} is too saturated ({sat:.2f})")

        if LARGE_AREA_RE.search(selector):
            for key in ("background", "background-color"):
                value = declarations.get(key)
                if value:
                    match = HEX_COLOR_RE.search(value)
                    if match and saturation(match.group(1)) > 0.32:
                        errors.append(f"{path}: {selector}: large-area {key} uses a saturated color")

        if BADGE_SELECTOR_RE.search(selector):
            has_width = "width" in declarations or "min-width" in declarations
            has_height = "height" in declarations or "min-height" in declarations
            if not (has_width and has_height):
                errors.append(f"{path}: {selector}: badge-like selector should define stable width/min-width and height/min-height")

        radius = declarations.get("border-radius")
        if radius and "var(--radius-" not in radius and "999" not in radius:
            match = re.search(r"(\d+(?:\.\d+)?)px", radius)
            if match and float(match.group(1)) > 10:
                errors.append(f"{path}: {selector}: border-radius above 10px should use a token")
    return errors


def lint_html(path: Path) -> list[str]:
    parser = StyleParser()
    parser.feed(path.read_text(encoding="utf-8"))
    if not parser.styles:
        return [f"{path}: no inline style block found"]
    return lint_css("\n".join(parser.styles), path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lightweight visual lint gates for CAST Docs HTML.")
    parser.add_argument("--input", action="append", type=Path, help="HTML file to lint. Repeatable.")
    parser.add_argument("--input-dir", type=Path, help="Directory of HTML files to lint.")
    args = parser.parse_args()

    paths: list[Path] = []
    if args.input:
        paths.extend(args.input)
    if args.input_dir:
        paths.extend(sorted(args.input_dir.glob("*.html")))
    if not paths:
        print("ERROR: provide --input or --input-dir", file=sys.stderr)
        return 1

    errors: list[str] = []
    for path in paths:
        errors.extend(lint_html(path))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"visual lint ok: {len(paths)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
