from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cast_docs_common import (
    ROOT,
    SUPPORTED_LOCALES,
    attr,
    esc,
    is_localized_object,
    is_object,
    locale_is_supported,
    normalize_locale,
)


DATA_IMAGE_RE = re.compile(r"^data:image/(?:png|jpe?g|gif|webp);base64,[A-Za-z0-9+/=\s]+$", re.IGNORECASE)


@dataclass
class RenderContext:
    active_locale: str
    locales: list[str]
    i18n: dict[str, Any]
    config_dir: Path
    repo_root: Path = ROOT
    metadata: dict[str, Any] | None = None
    code_index: int = 0


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
