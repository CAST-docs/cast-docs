from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from cast_docs_common import (
    CONFIG_DIR,
    as_list,
    attr,
    esc,
    is_localized_object,
    is_object,
    load_config,
    localized_value,
    text,
)
from cast_docs_context import RenderContext, default_locale_for_context, render_i18n_text, tr
from cast_docs_inline import render_chapter_icon, render_inline, render_text
from cast_docs_renderer_diagrams import render_diagram
from cast_docs_validation import collect_block_types


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
