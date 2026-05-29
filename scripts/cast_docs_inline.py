from __future__ import annotations

import html
from typing import Any

from cast_docs_common import (
    SUPPORTED_LOCALES,
    as_list,
    attr,
    esc,
    is_localized_object,
    is_object,
    localized_value,
    text,
)
from cast_docs_context import RenderContext, default_locale_for_context, href_kind


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
