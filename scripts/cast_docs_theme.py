from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from cast_docs_common import (
    CONFIG_DIR,
    TEMPLATE_DIR,
    CastDocsError,
    ProjectProfile,
    is_object,
    load_config,
    load_template_module,
    set_dotted_value,
    text,
)


HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
CSS_LENGTH_RE = re.compile(r"^(?:0|[0-9]+(?:\.[0-9]+)?(?:px|rem|em))$")
CSS_LINE_HEIGHT_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
CSS_MOTION_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)?m?s$")
CSS_CUBIC_BEZIER_RE = re.compile(r"^cubic-bezier\([0-9.,\s-]+\)$")
CSS_SAFE_STRING_RE = re.compile(r"^[^;{}<>]+$")


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

STYLE_DENSITY_PRESETS: dict[str, dict[str, Any]] = {
    "comfortable": {},
    "compact": {
        "typography.size.base": "14px",
        "typography.size.title": "30px",
        "space.8": "28px",
        "space.10": "34px",
        "radius.lg": "6px",
    },
}

STYLE_SURFACE_PRESETS: dict[str, dict[str, Any]] = {
    "flat": {"surface.shadow": "none"},
    "bordered": {"surface.shadow": "none"},
    "elevated": {"surface.shadow": "var(--shadow-sm)"},
}

STYLE_ACCENT_PRESETS: dict[str, dict[str, Any]] = {
    "default": {},
    "blue": {
        "modes.light.color.primary": "#315f9f",
        "modes.light.color.primarySoft": "#eef3fa",
        "modes.light.color.accent": "#52686a",
        "modes.dark.color.primary": "#9bb7d9",
        "modes.dark.color.primarySoft": "#182231",
        "modes.dark.color.accent": "#9ab4b1",
    },
    "teal": {
        "modes.light.color.primary": "#357277",
        "modes.light.color.primarySoft": "#edf5f5",
        "modes.light.color.accent": "#52686a",
        "modes.dark.color.primary": "#9bc7c6",
        "modes.dark.color.primarySoft": "#162525",
        "modes.dark.color.accent": "#9ab4b1",
    },
    "green": {
        "modes.light.color.primary": "#55745f",
        "modes.light.color.primarySoft": "#eef4ef",
        "modes.light.color.accent": "#52686a",
        "modes.dark.color.primary": "#9ebaa5",
        "modes.dark.color.primarySoft": "#1a241d",
        "modes.dark.color.accent": "#9ab4b1",
    },
    "amber": {
        "modes.light.color.primary": "#8a6d3b",
        "modes.light.color.primarySoft": "#f8f4ea",
        "modes.light.color.accent": "#52686a",
        "modes.dark.color.primary": "#c7b27e",
        "modes.dark.color.primarySoft": "#242117",
        "modes.dark.color.accent": "#9ab4b1",
    },
    "rose": {
        "modes.light.color.primary": "#9b4d49",
        "modes.light.color.primarySoft": "#faf0ef",
        "modes.light.color.accent": "#52686a",
        "modes.dark.color.primary": "#d09a95",
        "modes.dark.color.primarySoft": "#271b1a",
        "modes.dark.color.accent": "#9ab4b1",
    },
}

STYLE_PROFILE_KEYS = {"theme", "density", "surface", "accent", "tokenOverrides"}


def _merge_theme(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(parent)
    overrides = child.get("overrides", {})
    if isinstance(overrides, dict):
        for dotted, value in overrides.items():
            set_dotted_value(merged, dotted, value)
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


def style_profile_from_project(project: dict[str, Any] | None) -> dict[str, Any]:
    if not is_object(project):
        return {}
    style_profile = project.get("styleProfile")
    return style_profile if is_object(style_profile) else {}


def normalize_style_override_path(path: str) -> str | None:
    if path.startswith("color."):
        return f"modes.light.{path}"
    if path.startswith("dark.color."):
        return f"modes.dark.{path.removeprefix('dark.')}"
    if path.startswith("shadow."):
        return f"modes.light.{path}"
    if path.startswith("dark.shadow."):
        return f"modes.dark.{path.removeprefix('dark.')}"
    if path.startswith(("modes.light.color.", "modes.dark.color.", "modes.light.shadow.", "modes.dark.shadow.")):
        return path
    if path.startswith(("typography.size.", "typography.lineHeight.", "typography.weight.", "space.", "radius.", "motion.", "surface.")):
        return path
    return None


def get_dotted_value(source: dict[str, Any], dotted: str) -> Any:
    cursor: Any = source
    for key in dotted.split("."):
        if not is_object(cursor) or key not in cursor:
            return None
        cursor = cursor[key]
    return cursor


def style_value_is_allowed(path: str, value: Any) -> bool:
    if path.endswith(".color.primarySoft") or ".color." in path:
        return isinstance(value, str) and bool(HEX_COLOR_RE.match(value))
    if path.startswith("typography.size.") or path.startswith("space.") or path.startswith("radius."):
        return isinstance(value, str) and bool(CSS_LENGTH_RE.match(value))
    if path.startswith("typography.lineHeight."):
        return isinstance(value, str) and bool(CSS_LINE_HEIGHT_RE.match(value))
    if path.startswith("typography.weight."):
        return isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 900
    if path.startswith("motion."):
        if path == "motion.ease":
            return isinstance(value, str) and bool(CSS_CUBIC_BEZIER_RE.match(value))
        return isinstance(value, str) and bool(CSS_MOTION_RE.match(value))
    if ".shadow." in path:
        return isinstance(value, str) and bool(CSS_SAFE_STRING_RE.match(value))
    if path == "surface.shadow":
        return value in {"none", "var(--shadow-sm)", "var(--shadow-md)", "var(--shadow-lg)"}
    return False


def validate_style_profile(style_profile: Any, config_dir: Path, errors: list[str]) -> None:
    if style_profile is None:
        return
    if not is_object(style_profile):
        errors.append("project.json styleProfile must be an object")
        return

    for key in style_profile:
        if key not in STYLE_PROFILE_KEYS:
            errors.append(f"project.json styleProfile contains unsupported key: {key}")

    config = load_config("theme-tokens.json", config_dir)
    theme_ids = {theme["id"] for theme in config.get("themes", []) if is_object(theme) and isinstance(theme.get("id"), str)}
    theme_id = style_profile.get("theme")
    if theme_id is not None and theme_id not in theme_ids:
        errors.append(f"project.json styleProfile.theme is unknown: {theme_id}")
    active_theme_id = theme_id if isinstance(theme_id, str) and theme_id in theme_ids else text(config.get("defaultTheme") or "cast-default")
    try:
        active_theme = load_theme(active_theme_id, config_dir)
    except CastDocsError as exc:
        errors.append(str(exc))
        active_theme = {}

    density = style_profile.get("density")
    if density is not None and density not in STYLE_DENSITY_PRESETS:
        errors.append(f"project.json styleProfile.density must be one of: {', '.join(STYLE_DENSITY_PRESETS)}")
    surface = style_profile.get("surface")
    if surface is not None and surface not in STYLE_SURFACE_PRESETS:
        errors.append(f"project.json styleProfile.surface must be one of: {', '.join(STYLE_SURFACE_PRESETS)}")
    accent = style_profile.get("accent")
    if accent is not None and accent not in STYLE_ACCENT_PRESETS:
        errors.append(f"project.json styleProfile.accent must be one of: {', '.join(STYLE_ACCENT_PRESETS)}")

    token_overrides = style_profile.get("tokenOverrides")
    if token_overrides is None:
        return
    if not is_object(token_overrides):
        errors.append("project.json styleProfile.tokenOverrides must be an object")
        return
    for path, value in token_overrides.items():
        if not isinstance(path, str) or not path.strip():
            errors.append("project.json styleProfile.tokenOverrides keys must be non-empty strings")
            continue
        normalized = normalize_style_override_path(path)
        if normalized is None:
            errors.append(f"project.json styleProfile.tokenOverrides contains unsupported token: {path}")
            continue
        if get_dotted_value(active_theme, normalized) is None and normalized != "surface.shadow":
            errors.append(f"project.json styleProfile.tokenOverrides contains unknown token: {path}")
            continue
        if not style_value_is_allowed(normalized, value):
            errors.append(f"project.json styleProfile.tokenOverrides.{path} has an unsupported value")


def style_profile_overrides(style_profile: dict[str, Any]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    density = style_profile.get("density")
    if isinstance(density, str):
        overrides.update(STYLE_DENSITY_PRESETS.get(density, {}))
    surface = style_profile.get("surface")
    if isinstance(surface, str):
        overrides.update(STYLE_SURFACE_PRESETS.get(surface, {}))
    accent = style_profile.get("accent")
    if isinstance(accent, str):
        overrides.update(STYLE_ACCENT_PRESETS.get(accent, {}))
    token_overrides = style_profile.get("tokenOverrides")
    if is_object(token_overrides):
        overrides.update(token_overrides)
    return overrides


def apply_style_profile_to_theme(theme: dict[str, Any], style_profile: dict[str, Any]) -> dict[str, Any]:
    if not style_profile:
        return theme
    merged = copy.deepcopy(theme)
    for path, value in style_profile_overrides(style_profile).items():
        normalized = normalize_style_override_path(path)
        if normalized:
            set_dotted_value(merged, normalized, value)
    return merged


def theme_for_profile(profile: ProjectProfile | None, config_dir: Path = CONFIG_DIR) -> dict[str, Any]:
    config = load_config("theme-tokens.json", config_dir)
    style_profile = style_profile_from_project(profile.project if profile else None)
    theme_id = text(style_profile.get("theme") or config.get("defaultTheme") or "cast-default")
    return apply_style_profile_to_theme(load_theme(theme_id, config_dir), style_profile)


def compile_theme_root_css(theme: dict[str, Any]) -> str:
    modes = theme.get("modes", {})
    light_color = modes.get("light", {}).get("color", {}) if is_object(modes) else {}
    dark_color = modes.get("dark", {}).get("color", {}) if is_object(modes) else {}
    light_shadow = modes.get("light", {}).get("shadow", {}) if is_object(modes) else {}
    dark_shadow = modes.get("dark", {}).get("shadow", {}) if is_object(modes) else {}
    typography = theme.get("typography", {}) if is_object(theme.get("typography")) else {}

    def color_lines(color_map: dict[str, Any], indent: str) -> list[str]:
        lines = []
        for token, var in THEME_COLOR_TO_CSS_VAR.items():
            value = color_map.get(token) if is_object(color_map) else None
            if value:
                lines.append(f"{indent}{var}: {value};")
        return lines

    def shadow_lines(shadow_map: dict[str, Any], indent: str) -> list[str]:
        lines = []
        if is_object(shadow_map):
            for key, value in shadow_map.items():
                lines.append(f"{indent}--shadow-{key}: {value};")
        return lines

    light_body = ["  color-scheme: light dark;", *color_lines(light_color, "  "), *shadow_lines(light_shadow, "  ")]
    sans = typography.get("sans")
    mono = typography.get("mono")
    if sans:
        light_body.append(f"  --sans: {sans};")
    if mono:
        light_body.append(f"  --mono: {mono};")
    size = typography.get("size")
    if is_object(size):
        for key, value in size.items():
            light_body.append(f"  --font-{key}: {value};")
    line_height = typography.get("lineHeight")
    if is_object(line_height):
        for key, value in line_height.items():
            light_body.append(f"  --line-{key}: {value};")
    weight = typography.get("weight")
    if is_object(weight):
        for key, value in weight.items():
            light_body.append(f"  --weight-{key}: {value};")
    space = theme.get("space")
    if is_object(space):
        for key, value in space.items():
            light_body.append(f"  --space-{key}: {value};")
    radius = theme.get("radius")
    if is_object(radius):
        for key, value in radius.items():
            light_body.append(f"  --radius-{key}: {value};")
    motion = theme.get("motion")
    if is_object(motion):
        for key, value in motion.items():
            light_body.append(f"  --motion-{key}: {value};")
    surface = theme.get("surface")
    surface_shadow = surface.get("shadow") if is_object(surface) else None
    light_body.append(f"  --surface-shadow: {surface_shadow or 'none'};")
    light_block = ":root {\n" + "\n".join(light_body) + "\n}"

    dark_body = [*color_lines(dark_color, "    "), *shadow_lines(dark_shadow, "    ")]
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
    profile: ProjectProfile | None = None,
) -> str:
    root = compile_theme_root_css(theme_for_profile(profile, config_dir) if profile else load_theme(theme_id, config_dir))
    layout = load_template_module("styles.base.css", template_dir)
    return f"\n{root}\n{layout}"
