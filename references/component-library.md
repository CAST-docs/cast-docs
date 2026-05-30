# Component Library

This file defines planned reusable document components. It is a skeleton for the future renderer and examples.

Components are loaded on demand. A document should include only the components required by its document type, scenario skeleton, and available content.

Before adding a new component, check whether an existing component plus a clearer section title can represent the content.

The implementation target is to support the full component set in this file. On-demand composition controls when a component is rendered; it is not a reason to omit component implementations from the renderer.

## Component Selection Contract

Each reusable component should eventually define:

- Purpose.
- Required trigger.
- Optional trigger.
- JSON shape.
- HTML rendering rule.
- Allowed child content.
- Empty-state behavior.

The generator must record selected components in the assembly manifest before rendering. Strong triggers are mandatory. Optional triggers should be included only when they add new information.

Component availability and triggers should be represented in configuration so new scenarios can reuse existing components without renderer changes.

Scenario skeletons do not whitelist components. Any configured component may be used in any scenario when its trigger matches and it helps communicate the content. The renderer should validate the component payload, not block it because of the scenario name.

## Summary Block

Use for the concise document summary near the top of the page.

## Metadata Block

Use for status, owner, audience, updated date, and related metadata.

## Table Of Contents

Generate from section titles and stable IDs.

## Callout

Use for important notes, warnings, risks, and decisions.

Planned variants:

- `info`
- `warning`
- `danger`
- `success`

## Tables

Use tables for comparisons, requirements, risk registers, decision matrices, and rollout plans.

## Details Block

Use for optional background, alternatives, or supporting notes that should not dominate the main document flow.

## Code Block

Use for configuration, schema, API, or command examples when necessary. Rendered code blocks include line numbers, horizontal scrolling for long lines, and a renderer-owned copy button. The copy behavior must preserve the active locale when the code string is localized.

Do not use code blocks as a diagram fallback. Mermaid, PlantUML, Graphviz, and `flowchart` source are rejected by validation when published as code; use the diagram component instead.

Diff blocks use the same controlled monospace language, with line numbers, add/remove/warning/context states, and an optional line-level `highlight` flag for the exact line under discussion.

## Inline SVG Figure

Use only for simple self-contained diagrams. SVG must follow the controlled HTML profile.

Diagram components must support renderer-owned controls for zoom/lightbox viewing and one-click SVG or PNG download. Documents provide structured diagram content; the shared template provides the interaction. Supported structured diagram sources include flow, sequence, and ER-style entity relationship diagrams.

Final HTML must expose an inline SVG figure, not the source language and not a static SVG image data URI. A diagram created from Mermaid-like input should be translated into a structured diagram source or sanitized inline SVG before publication, then validated with the shared diagram viewer hook present.

## Media Grid

Use for visual evidence or format support examples. Media items may use self-contained `data:image` sources for PNG, JPG/JPEG, GIF, and WebP, or safe relative/http(s) sources when the document is allowed to reference external files. Each item requires alt text and may include a caption.

Repository-level reusable media should live under `.cast-docs/assets/`. The generator may reference those assets in media blocks when the current document needs them, and the renderer should preserve portability by embedding repository-local assets when the selected output mode requires a self-contained HTML artifact.

## Columns

Use for Lark-style side-by-side content where several peer items should be read as one row. A column may be pure inline content for visual distribution, or it may contain regular child blocks such as paragraphs, lists, tables, or code.

## Toggle View

Use when a document needs a built-in button to switch between two or more views, such as overview/source, table/chart, or before/after explanations. The JSON owns the views and labels; the renderer owns the JavaScript.

## Slider Control

Use when a document needs a controlled numeric adjustment with immediate visual feedback, such as dimming or brightening sample text. The JSON owns the label, range, initial value, and target content; the renderer owns the range input, output value, and progressive enhancement script. The initial supported effect is `opacity`.

## Acceptance Criteria

Use concise bullet lists with observable outcomes.

## Open Questions

Use explicit questions. Do not hide unknowns in vague prose.

## Inline Text Formatting

Prose-bearing fields (`paragraph`, `list`, `callout` body, table cells, `summary` body, `participants` responsibility, `action` description, `values-grid` body, `acceptance-criteria`, `open-questions`) accept inline runs in addition to plain strings. Runs carry typed marks — visual (`strong`, `em`, `code`, `del`, `u`, `mark`), semantic (`deprecated`, `term`, `metric`), and reference (`link`, `ref`). See Generation Contract → Inline Text Formatting for the full shape and rules.

## Shell Links

Optional topbar/footer navigation via `metadata.shellLinks` (component `shell-links`, default off). Add a home link back to a sibling landing page only when the document is part of a multi-page set that has an `index.html`; a standalone document gets none. See Generation Contract → Optional Shell Links.

## Logo Chrome

Optional topbar brand mark via `metadata.logo` (component `logo-chrome`, default off). Use it for the CAST Docs landing and example set, when the caller explicitly requests branded document chrome, or when `.cast-docs/project.json` declares a repository logo. The renderer embeds repository-local image files as data URIs, so generated HTML remains self-contained.

Prefer `.cast-docs/assets/logo.png` or another path under `.cast-docs/assets/` for repository-level logos. `alt` text is required.
