from __future__ import annotations

import copy
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
TEMPLATE_DIR = ROOT / "assets" / "template-modules"
SUPPORTED_LOCALES = ("en", "zh-CN")


class CastDocsError(Exception):
    pass


@dataclass
class ValidationResult:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class ProjectProfile:
    repo_root: Path
    profile_dir: Path
    project: dict[str, Any]
    preferences: dict[str, Any]
    i18n: dict[str, Any]
    glossary: dict[str, Any]
    writing_style: str
    present: bool = False


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CastDocsError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def load_config(name: str, config_dir: Path = CONFIG_DIR) -> Any:
    return load_json(config_dir / name)


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = load_json(path)
    if not isinstance(data, dict):
        raise CastDocsError(f"{path}: expected a JSON object")
    return data


def load_template_module(name: str, template_dir: Path = TEMPLATE_DIR) -> str:
    path = template_dir / name
    if not path.exists():
        raise CastDocsError(f"template module not found: {path}")
    return path.read_text(encoding="utf-8")


def resolve_inside_root(root: Path, relative_path: str, label: str) -> Path:
    if not relative_path:
        raise CastDocsError(f"{label} must be a non-empty repository-relative path")
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise CastDocsError(f"{label} must be repository-relative: {relative_path}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise CastDocsError(f"{label} must stay inside the repository: {relative_path}") from exc
    return resolved


def path_inside_root(root: Path, relative_path: str, label: str, errors: list[str]) -> Path | None:
    try:
        return resolve_inside_root(root, relative_path, label)
    except CastDocsError as exc:
        errors.append(str(exc))
        return None


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


def is_localized_object(value: Any) -> bool:
    return is_object(value) and any(locale in value for locale in SUPPORTED_LOCALES)


def locale_is_supported(locale: Any) -> bool:
    return isinstance(locale, str) and locale in SUPPORTED_LOCALES


def normalize_locale(locale: Any, fallback: str = "en") -> str:
    return locale if locale_is_supported(locale) else fallback


def localized_value(value: Any, locale: str, fallback: str = "en") -> Any:
    if not is_localized_object(value):
        return value
    if locale in value:
        return value[locale]
    if fallback in value:
        return value[fallback]
    for supported_locale in SUPPORTED_LOCALES:
        if supported_locale in value:
            return value[supported_locale]
    return ""


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if is_object(value) and is_object(merged.get(key)):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def get_dotted_value(source: dict[str, Any], dotted: str) -> Any:
    cursor: Any = source
    for key in dotted.split("."):
        if not is_object(cursor) or key not in cursor:
            return None
        cursor = cursor[key]
    return cursor


def set_dotted_value(target: dict[str, Any], dotted: str, value: Any) -> None:
    cursor = target
    keys = dotted.split(".")
    for key in keys[:-1]:
        next_value = cursor.get(key)
        if not is_object(next_value):
            next_value = {}
            cursor[key] = next_value
        cursor = next_value
    cursor[keys[-1]] = copy.deepcopy(value)
