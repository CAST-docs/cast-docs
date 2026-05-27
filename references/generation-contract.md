# Generation Contract

This contract captures reusable architecture patterns from prior HTML report generators while keeping CAST Docs independent from their visual style.

## What To Borrow

Borrow these mechanisms:

- A type declaration before generation.
- A stable scenario skeleton for each common document scene.
- A compact assembly manifest that records selected sections and components.
- A fixed renderer-owned base template that is not copied into model context.
- Strong and optional component triggers.
- Small, sanitized examples that cover component behavior.
- Verification gates after rendering.

Do not borrow these implementation details by default:

- Brand-specific colors, spacing, logos, watermarks, or typography.
- External CDN scripts or runtime services.
- Large JavaScript interaction bundles.
- Raw HTML injection without escaping or validation.

Allowed adaptation:

- Diagram zoom and download may be supported through renderer-owned inline JavaScript, with no external CDN dependency and no user-authored script blocks.
- Slider controls may be supported through renderer-owned inline JavaScript when the JSON describes the range, value, and target content.

## Required Declaration

Before rendering, the generator should declare:

- Base document type.
- Scenario skeleton, or `none`.
- Required sections in final order.
- Required components.
- Optional components triggered by the source material.
- Components intentionally omitted.

Example:

```text
Type: engineering-plan.
Scenario: problem-investigation.
Required sections: Background, Problem symptoms, Impact scope, Investigation path, Core logs and evidence, Root cause, Mitigation and fix, Validation, Prevention measures, Open questions.
Required components: Summary Block, Metadata Block, Table Of Contents, Callout, Open Questions.
Optional components triggered: Tables for risk register, Code Block for log excerpts.
Omitted components: Inline SVG Figure, because no diagram is needed.
```

## Manifest Field Semantics

The `components.required / optional / omitted` arrays describe what this specific document declares, not the full registry policy:

- `required`: components the document actually uses and that are mandatory for its document type or scenario.
- `optional`: components the document uses because the source material triggered them, even though the scenario does not require them.
- `omitted`: components that the scenario allows but the source did not need; recording them helps future review.

Skip globally implicit components such as `section` and `paragraph` — they are structural defaults, not authoring choices. The renderer applies them regardless of manifest content.

## Assembly Manifest

The document JSON should include a compact manifest, either as a top-level field or a renderer-side companion object.

The manifest should be built from configuration registries for document types, scenario skeletons, and components. Scenario coverage should grow by editing configuration first, not by adding renderer conditionals.

Minimum shape:

```json
{
  "documentType": "engineering-plan",
  "scenario": "problem-investigation",
  "sections": ["background", "problem-symptoms", "impact-scope"],
  "components": {
    "required": ["summary-block", "metadata-block", "toc"],
    "optional": ["callout", "code-block"],
    "omitted": ["inline-svg-figure"]
  }
}
```

The manifest is a generation and validation aid. It should not force the final HTML to expose internal planning details.

## Template Boundary

The shared template, CSS, and renderer behavior belong to the renderer, not the prompt. The model should emit structured content and component intent. The renderer should:

- Load the shared base template.
- Resolve theme tokens and layout shell from configuration.
- Escape user-provided text by default.
- Render approved components from the structured JSON.
- Reject unknown tags, attributes, classes, and URL schemes.
- Validate the final HTML profile.
- Provide approved progressive enhancements from the shared template, not from generated content.

This keeps output consistent and reduces token use.

For document sets, the model should emit document JSON files plus a set manifest. The renderer owns index generation, sidebar/topbar composition, and previous/next pagination.

## Optional Shell Links

Document chrome may expose user-meaningful navigation links, but only when the caller provides them. The renderer should not invent breadcrumbs, implementation status, theme names, or layout names for display.

Use `metadata.shellLinks` for optional links such as:

```json
{
  "metadata": {
    "title": "CAST Docs 模块化文档样例",
    "language": "zh-CN",
    "shellLinks": [
      {
        "label": "文档首页",
        "href": "index.html",
        "placement": "topbar"
      }
    ]
  }
}
```

Rules:

- Render nothing when `shellLinks` is empty.
- Keep labels business-readable, such as `文档首页`, `返回仓库`, or `设计总览`.
- Allow only anchor, relative, HTTP, and HTTPS hrefs.
- Use the layout-owned `topbar-links` slot rather than embedding links inside generated prose.

Home navigation is an optional capability (`shell-links`, default off). When the document is one of a multi-page set that has a sibling landing or index page — for example an `examples/*.html` page next to `index.html` — add a single topbar link back to it, such as `{"label": "CAST Docs", "href": "../index.html"}`. A standalone document gets none. This is the only shell link the generator may add on its own; all others must come from the caller.

## Optional Logo

Document chrome may expose a renderer-owned logo when the caller provides `metadata.logo`.

Use it for CAST Docs site pages, example pages, and document sets that have a stable brand mark:

```json
{
  "metadata": {
    "logo": {
      "src": "assets/cast-docs-logo.png",
      "alt": "CAST Docs logo",
      "href": "index.html"
    }
  }
}
```

Rules:

- `src` allows `data:image` sources or repository-local PNG/JPG/GIF/WebP paths.
- Repository-local paths are resolved from the repository root and embedded as data URIs during render, preserving single-file HTML output.
- `alt` is required and may be localized.
- `href` is optional and follows the same safe scheme rules as shell links.
- Do not add a logo to standalone user documents unless the caller asks for branded chrome.

## CLI Boundary

The renderer should expose a small CLI surface:

```sh
python3 scripts/render_html.py \
  --input examples/problem-investigation.json \
  --output dist/problem-investigation.html
```

Validation should be available as separate commands and as optional render steps:

```sh
python3 scripts/validate_doc_json.py --input examples/problem-investigation.json
python3 scripts/validate_html.py --input dist/problem-investigation.html
python3 scripts/render_html.py --input doc.json --output doc.html --validate
```

The CLI should not require the model to copy templates, CSS, or renderer internals into context.

## Bilingual Documents

When the caller asks for a bilingual document, keep both languages in the same document JSON and set `metadata.locales`.

```json
{
  "metadata": {
    "title": {
      "en": "Bilingual rendering decision",
      "zh-CN": "双语渲染方案决策"
    },
    "language": "en",
    "locales": ["en", "zh-CN"]
  }
}
```

Human-readable fields may use a localized object whose keys are supported locale ids. The renderer writes both language variants into the same HTML and exposes a top-right language switcher. `metadata.language` is the initial visible language.

Allowed localized fields include document and section titles, shell link labels, summary labels, inline prose fields, list items, table headers and cells, callout titles, details summaries, diagram labels, diff labels and lines, participant names and roles, source reference labels and notes, file notes, action titles and prompts, values-grid titles, acceptance criteria, and open questions.

Keep machine fields single-valued: ids, paths, URLs, code, language tags, status, scenario names, document type names, component ids, and section ids should not be localized.

## Component Trigger Policy

Each component has a trigger level:

- `required`: always present for the selected document type or scenario.
- `strong`: present when source material contains a clear signal.
- `optional`: present only when it improves clarity without repeating content.
- `forbidden`: unavailable under the controlled HTML profile.

The generator should not include optional components for decoration or recap. Components must carry new information.

Scenario skeletons do not restrict component choice. They provide the required section scaffold. Within each section, the generator may select any configured component whose trigger matches the source material or whose use makes the explanation clearer. For example, a `problem-investigation` document may include a sequence diagram for a call chain, a diff block for code or schema differences, a table for impact scope, and details blocks for core logs.

## Inline Text Formatting

Prose-bearing fields accept either a plain string or an array of **runs**. A plain string is escaped as-is. An array carries typed inline marks whose semantics are preserved in the JSON sidecar, not just the visual style — this is the point: a mark such as `deprecated`, `metric`, or `ref` is machine-readable, not decorative.

Fields that accept inline runs: `paragraph.text`, `list.items[]`, `callout.body`, table `rows[][]` cells, `summary.items[].body`, `participants.items[].responsibility`, `action.description`, `values-grid.items[].body`, `acceptance-criteria.items[]`, and `open-questions.questions[]`. Titles, labels, table headers, `code`, and diff lines stay plain strings.

A run is `{ "text": string, "marks"?: array }`. Each mark is a string shorthand or an object that carries data:

- Visual: `strong`, `em`, `code`, `del`, `u`, `mark`.
- Semantic: `deprecated`, `term` (+ optional `definition`), `metric` (+ optional `unit`, `value`).
- Reference: `{ "type": "link", "href": ... }`; `{ "type": "ref", "path": ..., "line"?: integer, "url"?: ... }`.

```json
{ "type": "paragraph", "text": [
  { "text": "Timeout cut from " },
  { "text": "30s", "marks": ["del"] },
  { "text": " to " },
  { "text": "3s", "marks": [{ "type": "metric", "unit": "s", "value": 3 }] },
  { "text": " in " },
  { "text": "inventory_client.go:88", "marks": [{ "type": "ref", "path": "services/checkout/inventory_client.go", "line": 88 }] }
]}
```

Rules:

- Marks nest innermost-first in array order: `["code", "deprecated"]` renders `<span data-mark="deprecated"><code>…</code></span>`.
- Visual marks render as their tag. Semantic marks render as `<span data-mark="TYPE">`; rich attributes (`unit`, `value`, `definition`) live in the sidecar JSON, not the rendered span. `link` renders an anchor; `ref` renders code, linked when `url` is present.
- `link.href` and `ref.url` allow only anchor, relative, HTTP, and HTTPS schemes — never `mailto:`, `tel:`, or `javascript:`.
- An anchor href (`#id`) must resolve to a real section or block id, or HTML validation fails.

## Verification Gates

At minimum, generation should verify:

- Required sections are present and ordered.
- Stable section IDs exist and match the table of contents.
- Only allowed tags, attributes, classes, and link schemes are used.
- User-provided text is escaped unless a field is explicitly trusted by schema.
- The final HTML has no unresolved template placeholders.
- No unused component shell is rendered.
- Inline marks use only the approved vocabulary; `link`/`ref` hrefs use allowed schemes and `#anchor` targets resolve.
