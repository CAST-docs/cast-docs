from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Any

from cast_docs_common import (
    CONFIG_DIR,
    ROOT,
    TEMPLATE_DIR,
    CastDocsError,
    ProjectProfile,
    as_list,
    attr,
    esc,
    is_object,
    load_config,
    load_template_module,
    localized_value,
    normalize_locale,
    text,
)
from cast_docs_context import (
    DATA_IMAGE_RE,
    RenderContext,
    default_locale_for_context,
    document_locales,
    locale_display_label,
    media_src_kind,
    render_i18n_text,
    tr,
)
from cast_docs_inline import render_text
from cast_docs_profile import apply_project_profile, project_display_name, project_owner_display_name
from cast_docs_renderer_blocks import block_types_in_doc, render_block
from cast_docs_theme import base_css
from cast_docs_validation import collect_block_types


SUPPORTED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


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
    breadcrumb_title = metadata.get("breadcrumbTitle") or title_value
    owner_name = project_owner_display_name(metadata, profile)
    if owner_name:
        parts.append(f"<span class=\"topbar-org\">{esc(owner_name)}</span>")
    project_name = project_display_name(profile)
    if project_name:
        parts.append(f"<span class=\"topbar-project\">{esc(project_name)}</span>")
    if not project_name or not same_localized_text(breadcrumb_title, project_name, ctx):
        parts.append(f"<span class=\"topbar-doc\">{render_text(breadcrumb_title, ctx)}</span>")
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
        "STYLE": base_css(config_dir=config_dir, template_dir=template_dir, profile=profile),
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
