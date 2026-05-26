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

## Component Trigger Policy

Each component has a trigger level:

- `required`: always present for the selected document type or scenario.
- `strong`: present when source material contains a clear signal.
- `optional`: present only when it improves clarity without repeating content.
- `forbidden`: unavailable under the controlled HTML profile.

The generator should not include optional components for decoration or recap. Components must carry new information.

Scenario skeletons do not restrict component choice. They provide the required section scaffold. Within each section, the generator may select any configured component whose trigger matches the source material or whose use makes the explanation clearer. For example, a `problem-investigation` document may include a sequence diagram for a call chain, a diff block for code or schema differences, a table for impact scope, and details blocks for core logs.

## Verification Gates

At minimum, generation should verify:

- Required sections are present and ordered.
- Stable section IDs exist and match the table of contents.
- Only allowed tags, attributes, classes, and link schemes are used.
- User-provided text is escaped unless a field is explicitly trusted by schema.
- The final HTML has no unresolved template placeholders.
- No unused component shell is rendered.
