---
name: cast-docs
description: Generate standardized, self-contained HTML documents for engineering specs, plans, product requirements, decision records, and research notes. Use when the user wants portable Chrome-viewable documentation, GitHub Pages friendly static docs, or a controlled replacement for Markdown-based technical documents.
---

# CAST Docs

CAST Docs means Component Assembly Styled Templates.

Use this skill to produce stable, readable, self-contained HTML documents from notes, outlines, drafts, or instructions. The intended output is a static document, not a wiki product, CMS, web app, or collaborative editor.

## Workflow

1. Determine the document type.
2. Extract or infer metadata.
3. Convert the input into a structured document JSON representation.
4. Validate the JSON representation.
5. Render a complete single-file HTML document.
6. Validate the generated HTML against the controlled profile.
7. Return the `.html` file or HTML content, depending on the environment.

Prefer the JSON intermediate representation before HTML rendering. This keeps document structure deterministic and prevents formatting drift.

## Initial Document Types

Support these document types:

- `engineering-spec`
- `engineering-plan`
- `product-requirement`
- `decision-record`
- `research-note`

Read `references/document-types.md` before choosing required sections.

## Output Rules

- Generate complete HTML files, not fragments.
- Inline CSS only.
- Do not depend on external CSS, JavaScript, fonts, CDNs, images, or runtime services.
- Default to zero JavaScript.
- Use conservative links only: anchors, relative paths, `http:`, and `https:`.
- Escape user-provided text.
- Do not invent critical facts; mark unknowns explicitly.

## Design Influences

Borrow principles, not product scope:

- BookStack: simple, readable pages that work well as standalone documents.
- Wiki.js: Git-friendly publishing and GitHub Pages compatibility.
- Docmost: reusable document blocks and structured document composition.
- Tiptap / ProseMirror: schema discipline through a controlled JSON representation.

## Resources

- `references/document-types.md`: document types and required sections.
- `references/html-profile.md`: allowed HTML profile and safety rules.
- `references/component-library.md`: reusable document components.
- `references/writing-style.md`: writing and editing rules.
- `references/examples.md`: planned examples.
- `assets/base-template.html`: planned single-file HTML template.
- `scripts/`: planned renderer, JSON validator, HTML validator, and index builder.

## Skeleton Status

This repository currently contains the skill skeleton only. Scripts and templates are placeholders until the implementation phase.
