# Project Profile

`cast-a-doc` can be used in any repository without repository-local setup. When a team wants the skill to remember repository-specific documentation choices, use a repository-level `.cast-docs/` directory.

The project profile is not hidden model memory. It is a reviewable, versioned configuration layer that describes how this repository writes CAST Docs documents.

## Goals

- Keep repository-specific documentation rules close to the code they describe.
- Make repeated document generation consistent without copying prompt instructions.
- Preserve team decisions such as language, terminology, templates, output paths, and brand assets.
- Keep shared team rules separate from private user preferences and generated drafts.
- Allow the skill to ask fewer repeat questions while still making uncertain choices explicit.

## Configuration Layers

`cast-a-doc` merges configuration in this order:

1. Built-in CAST Docs defaults from `config/`, `references/`, and `examples/`.
2. Repository project profile from `.cast-docs/`.
3. User request for the current document.

Later layers override earlier layers only for the fields they explicitly set. The current user request always has the highest priority.

## Directory Layout

Recommended repository profile layout:

```text
.cast-docs/
  project.json
  preferences.json
  i18n.json
  glossary.json
  writing-style.md
  templates/
    problem-investigation.json
    decision-record.json
    product-requirement.json
  examples/
    good-investigation.json
    good-decision-record.json
  assets/
    logo.png
    icons/
    screenshots/
  out/
```

`project.json` declares stable repository metadata, brand, output defaults, and style profile. `preferences.json` declares generation defaults. `i18n.json`, `glossary.json`, and `writing-style.md` constrain language and wording. `templates/` and `examples/` provide reusable structure. `assets/` contains repository-owned visual assets that may be embedded into generated HTML. `out/` is for local generated output and should usually be ignored by Git.

## Shared Versus Local State

Commit these files when they express team policy:

- `.cast-docs/project.json`
- `.cast-docs/preferences.json`
- `.cast-docs/i18n.json`
- `.cast-docs/glossary.json`
- `.cast-docs/writing-style.md`
- `.cast-docs/templates/`
- `.cast-docs/examples/`
- `.cast-docs/assets/`

Do not commit private or temporary state by default:

- `.cast-docs/out/`
- `.cast-docs/local/`
- `.cast-docs/cache/`
- Generated drafts that contain private investigation notes.

Recommended `.cast-docs/.gitignore`:

```gitignore
out/
local/
cache/
*.tmp
```

If a generated HTML file is intended to be shared with the team, write it outside `.cast-docs/out/`, usually under `docs/cast-docs/`.

## project.json

Example:

```json
{
  "version": 1,
  "name": "checkout-service",
  "defaultLocale": "zh-CN",
  "defaultDocumentType": "engineering-plan",
  "defaultScenario": "problem-investigation",
  "owner": "Checkout Platform",
  "audience": ["engineering", "product"],
  "output": {
    "defaultDir": "docs/cast-docs",
    "localDir": ".cast-docs/out",
    "filenamePattern": "{date}-{slug}.html"
  },
  "brand": {
    "logo": {
      "src": ".cast-docs/assets/logo.png",
      "alt": "Checkout Platform"
    }
  },
  "styleProfile": {
    "theme": "cast-default",
    "density": "compact",
    "surface": "bordered",
    "accent": "blue",
    "tokenOverrides": {
      "color.primary": "#315f9f",
      "radius.lg": "6px"
    }
  }
}
```

Rules:

- `version` is required.
- Paths are repository-relative.
- `defaultLocale` should match a locale declared in `i18n.json` when that file exists.
- `brand.logo.src` may point to a repository-local PNG, JPG/JPEG, GIF, WebP, or a `data:image` value.
- The renderer embeds repository-local logos as data URIs, preserving single-file HTML output.
- `styleProfile` is the standard project-level styling entry point. It chooses approved renderer presets and token overrides; it does not allow arbitrary CSS or document-level class names.

### styleProfile

`styleProfile` lets a repository brand CAST Docs output while preserving deterministic, validated HTML.

Supported fields:

- `theme`: currently selects a built-in theme such as `cast-default`.
- `density`: `comfortable` or `compact`.
- `surface`: `flat`, `bordered`, or `elevated`.
- `accent`: `default`, `blue`, `teal`, `green`, `amber`, or `rose`.
- `tokenOverrides`: a small map of approved design-token overrides.

Allowed `tokenOverrides` paths include:

- `color.<token>` for light-mode semantic colors.
- `dark.color.<token>` for dark-mode semantic colors.
- `typography.size.<token>`, `typography.lineHeight.<token>`, and `typography.weight.<token>`.
- `space.<token>`, `radius.<token>`, and `motion.<token>`.

Rules:

- Values are validated before render. Unknown token paths fail profile validation.
- Color overrides must be hex colors.
- Size, spacing, and radius overrides must use simple CSS lengths such as `6px`, `1rem`, or `0`.
- `styleProfile` changes renderer-owned CSS variables. Document JSON should still express semantic blocks such as `summary`, `table`, and `callout`, not visual class names.

## preferences.json

Example:

```json
{
  "version": 1,
  "scenarioDefaults": {
    "problem-investigation": {
      "documentType": "engineering-plan",
      "template": ".cast-docs/templates/problem-investigation.json",
      "preferredComponents": ["summary-block", "metadata-block", "toc", "callout", "table", "code-block", "open-questions"],
      "omitWhenEmpty": ["diagram", "media-grid", "diff-block"]
    }
  },
  "writing": {
    "summaryStyle": "owner-facing",
    "unknownPolicy": "mark-explicitly",
    "evidencePolicy": "cite-source-or-mark-missing"
  }
}
```

Rules:

- Preferences tune generation; they do not bypass schema, component, or HTML validation.
- `preferredComponents` are hints, not a command to render empty components.
- If a preference conflicts with the current user request, the user request wins.

## i18n.json

Example:

```json
{
  "version": 1,
  "locales": ["zh-CN", "en"],
  "defaultLocale": "zh-CN",
  "fallbackLocale": "en",
  "titlePolicy": "preserve-source-language",
  "terminologyPolicy": "use-glossary-first"
}
```

The profile may override the built-in `config/i18n.json` defaults for this repository. Machine-readable fields such as ids, paths, URLs, code, component ids, and scenario ids must remain single-valued and should not be localized.

## glossary.json

Example:

```json
{
  "version": 1,
  "terms": [
    {
      "term": "SKU",
      "meaning": "Stock Keeping Unit",
      "translation": {
        "zh-CN": "SKU"
      },
      "notes": "Do not translate as 库存单位 in product docs."
    }
  ]
}
```

Use the glossary for product names, internal system names, acronyms, and terms that should not be translated literally.

## writing-style.md

The repository writing style extends `references/writing-style.md`. It should state durable team rules, such as:

- Preferred language.
- Whether to write for owner teams, product reviewers, or implementation engineers.
- Required evidence format.
- Terms to avoid.
- Section naming conventions.

The file should stay short. If it grows into a full style guide, split examples into `.cast-docs/examples/`.

## Templates And Examples

Templates are partial or complete document JSON files that provide reusable structure. Examples are known-good complete fixtures for the repository.

Rules:

- Templates must still produce valid document JSON after the current request fills missing content.
- Templates may preselect document type, scenario, required sections, and preferred blocks.
- Examples should be sanitized and small enough to inspect quickly.
- A repository template must not introduce new block types unless CAST Docs supports them through the configured component registry.

## Assets

Repository assets live under `.cast-docs/assets/` when they are part of document identity or reusable evidence.

Allowed uses:

- `metadata.logo` for document chrome.
- `media` blocks for reusable visual evidence.
- Diagram fallback images when represented by an approved media block.

Rules:

- Prefer PNG, JPG/JPEG, GIF, WebP, or `data:image` sources.
- Keep assets repository-local when the generated HTML must be portable.
- Provide alt text for every image.
- Do not use remote assets for logos unless the caller explicitly accepts a non-self-contained dependency.

## Output Path Policy

When an agent generates HTML for a user:

1. If the user provides an explicit output path, use it.
2. Otherwise, if `.cast-docs/project.json` defines `output.defaultDir`, propose that path for team-shareable documents.
3. Otherwise, ask the user to choose between:
   - `docs/cast-docs/<slug>.html` for committed/shareable docs.
   - `.cast-docs/out/<slug>.html` for local preview or private drafts.

Do not silently write final user documents to an arbitrary repository root path. Example scripts may still use `out.html` as a smoke-test default, but skill-driven generation should follow the policy above.

## Initialization Policy

Do not create `.cast-docs/` without user intent. When a user asks `cast-a-doc` to remember repository-specific settings, initialize the smallest useful profile:

```text
.cast-docs/
  project.json
  preferences.json
  writing-style.md
  assets/
  templates/
  examples/
  .gitignore
```

If the repository already has a profile, read it before generating and preserve user edits. Add or change profile files only when the user asks to update repository defaults or confirms a proposed change.

## Validation

Project profile validation should be layered:

- Profile JSON is syntactically valid.
- Declared paths stay inside the repository.
- Declared locales are consistent across `project.json` and `i18n.json`.
- Template JSON passes the normal CAST Docs document validator after request content is applied.
- Asset paths exist when referenced by `metadata.logo` or reusable media.

Profile validation should report actionable errors and should not mutate the profile.
