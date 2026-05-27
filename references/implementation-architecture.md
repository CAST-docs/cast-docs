# Implementation Architecture

CAST Docs should be implemented as a config-driven static document renderer. The goal is broad scenario coverage without hard-coding every scenario into Python branches.

## Core Decisions

- Cover all planned document types and scenario skeletons through configuration.
- Implement the full reusable component set.
- Render components only when the assembly manifest selects them.
- Keep the shared template, CSS, schema, and validators outside model context.
- Keep validation lightweight: profile checks, contract checks, and unresolved-placeholder checks, not browser-grade HTML sanitization.
- Keep interactive features centralized in the shared template.

## Configuration Model

Use small registry files as the source of truth:

```text
config/
  document-types.json
  scenario-skeletons.json
  components.json
  html-profile.json
  layouts.json
  theme-tokens.json
  interactions.json
```

Expected responsibilities:

- `document-types.json`: base document type names, purpose, required sections, default metadata.
- `scenario-skeletons.json`: scenario names, matching hints, recommended base types, required section order, required components.
- `components.json`: component ids, purpose, trigger level, JSON shape id, renderer id, allowed semantic classes.
- `html-profile.json`: allowed tags, attributes, classes, and URL schemes.
- `layouts.json`: single-document and document-set shells, slots, navigation models, and layout-selected interactions.
- `theme-tokens.json`: theme variables for colors, typography, spacing, radius, shadow, and motion.
- `interactions.json`: approved progressive enhancements and required template hooks.

Renderer code should consume these registries. Adding a new scenario should usually mean adding config and examples, not changing renderer control flow.

## Runtime Pipeline

1. Load registries.
2. Read document JSON.
3. Validate manifest against document type, scenario, and component registries.
4. Validate section order and required sections.
5. Render with the shared base template.
6. Render selected components from structured JSON.
7. Embed approved metadata logos as data URIs when `metadata.logo` references a repository-local image.
8. Validate the final HTML profile.
9. Write the output file.

Scenario validation should enforce required sections and required components, but it should not reject additional configured components. Extra components are valid when they appear in the manifest and their block payload matches the component schema.

## Document JSON Shape

The document JSON should be compact and renderer-friendly:

```json
{
  "metadata": {
    "title": "Example",
    "language": "zh-CN",
    "status": "draft",
    "owner": "unknown",
    "updatedAt": "2026-05-13"
  },
  "manifest": {
    "documentType": "engineering-plan",
    "scenario": "problem-investigation",
    "sections": ["background", "problem-symptoms"],
    "components": {
      "required": ["summary-block", "metadata-block", "toc"],
      "optional": ["callout", "code-block"],
      "omitted": []
    }
  },
  "sections": [
    {
      "id": "background",
      "title": "Background",
      "blocks": [
        {"type": "paragraph", "text": "Known context."}
      ]
    }
  ]
}
```

The exact schema can evolve, but the renderer should avoid raw HTML fields by default. Rich content should be represented as typed blocks.

## CLI Contract

Primary render command:

```sh
python3 scripts/render_html.py \
  --input examples/problem-investigation.json \
  --output dist/problem-investigation.html \
  --validate
```

Implemented options:

```text
--config-dir config
--validate
```

Separate validation commands:

```sh
python3 scripts/validate_doc_json.py --input examples/problem-investigation.json --config-dir config
python3 scripts/validate_html.py --input dist/problem-investigation.html --config-dir config
```

Index command:

```sh
python3 scripts/build_index.py --input-dir dist --output dist/index.html
```

## Lightweight HTML Validator

The validator should stay intentionally small. It should verify generated output, not sanitize arbitrary internet HTML.

Required checks:

- Document has doctype, `html`, `head`, `body`, title, inline style, article, header, toc, sections, and footer.
- Tags are in the allowed tag list.
- Attributes are in the allowed attribute list for each tag.
- Classes are known semantic classes from `html-profile.json` and `components.json`.
- Links use allowed schemes: anchor, relative path, `http`, and `https`.
- No event handler attributes.
- No external resource tags.
- Renderer-owned scripts match approved interaction ids; content-authored scripts are rejected.
- No unresolved template placeholders.
- Table of contents links point to existing section ids.
- Required sections from the manifest are present in order.
- No unused component shell is rendered.

Out of scope:

- Full browser layout verification.
- JavaScript execution.
- CSS linting beyond checking that styles are inline and owned by the template.
- Sanitizing arbitrary user HTML pasted into raw fields.

This keeps validation cheap while still catching the failures that matter for deterministic static docs.

## Development Readiness Checklist

Implemented contract files:

- `schemas/doc.schema.json`
- `config/document-types.json`
- `config/scenario-skeletons.json`
- `config/components.json`
- `config/html-profile.json`
- `config/layouts.json`
- `config/theme-tokens.json`
- `config/interactions.json`
- `examples/` fixtures covering every configured scenario

Implemented P0 scripts:

- `scripts/cast_docs_core.py`
- `scripts/validate_doc_json.py`
- `scripts/render_html.py`
- `scripts/validate_html.py`

Still planned:

- `scripts/build_index.py` for document-set index generation.
- Full template-module extraction from the current renderer-owned CSS/JS strings.
- Visual lint gates for saturation, fixed badge dimensions, and large color areas.

The fixtures are the practical guardrail for "cover all scenarios": every scenario in config should have at least one example JSON.
