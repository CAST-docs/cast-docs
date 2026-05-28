---
name: cast-docs
description: Generate standardized, self-contained HTML documents for engineering specs, plans, product requirements, decision records, and research notes. Use when the user wants portable Chrome-viewable documentation, GitHub Pages friendly static docs, or a controlled replacement for Markdown-based technical documents.
---

# CAST Docs

CAST Docs means Component Assembly Styled Templates.

Use this skill to produce stable, readable, self-contained HTML documents from notes, outlines, drafts, or instructions. The intended output is a static document, not a wiki product, CMS, web app, or collaborative editor.

## Workflow

1. Determine the document type.
2. Check whether the target repository has a `.cast-docs/` project profile.
3. Extract or infer metadata, applying project profile defaults when present.
4. Declare the scenario skeleton and component selection plan.
5. Convert the input into a structured document JSON representation.
6. Validate the JSON representation.
7. Choose an output path according to the user request or project profile.
8. Render a complete single-file HTML document.
9. Validate the generated HTML against the controlled profile.
10. Return the `.html` file or HTML content, depending on the environment.

Prefer the JSON intermediate representation before HTML rendering. This keeps document structure deterministic and prevents formatting drift.

## Design Laws

Read `references/design-laws.md` before implementation or generation decisions. The laws are binding:

- Generated HTML must keep one consistent structure, class vocabulary, and visual style.
- Load only the components and rendering behavior needed by the selected document type and scenario.
- Apply a scenario-specific default skeleton when the user intent implies one.
- Prefer reuse of existing schema fragments, components, templates, and examples before adding new structures.
- Apply repository-level `.cast-docs/` project profile defaults only when they are explicit and reviewable.

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
- Default to zero JavaScript for document content. Renderer-owned inline JavaScript is allowed only for approved progressive enhancements such as diagram zoom/download.
- Use conservative user-content links only: anchors, relative paths, `http:`, and `https:`.
- Escape user-provided text.
- Do not invent critical facts; mark unknowns explicitly.
- When a document belongs to the CAST Docs site or example set, add `metadata.logo` with `src: "assets/cast-docs-logo.png"` so the renderer can embed the logo in the document chrome.
- For user documents, do not silently write final HTML to an arbitrary repository root path. If the user does not provide a path and the repository profile does not define an output default, ask whether to use `docs/cast-docs/<slug>.html` for shareable docs or `.cast-docs/out/<slug>.html` for local drafts.
- Read `.cast-docs/project.json` before generation when it exists. Treat `.cast-docs/assets/` as the preferred place for repository-level logos and reusable visual assets.

## Design Influences

Borrow principles, not product scope:

- BookStack: simple, readable pages that work well as standalone documents.
- Wiki.js: Git-friendly publishing and GitHub Pages compatibility.
- Docmost: reusable document blocks and structured document composition.
- Tiptap / ProseMirror: schema discipline through a controlled JSON representation.

## Resources

- `config/`: configuration registries for document types, scenario skeletons, components, HTML profile, layouts, theme tokens, and approved interactions.
- `schemas/doc.schema.json`: structured document JSON contract.
- `examples/`: compact fixtures covering configured scenario skeletons.
- `references/design-laws.md`: binding architecture laws for consistency, on-demand composition, scenario skeletons, and reuse.
- `references/generation-contract.md`: type declaration, assembly manifest, template boundary, component trigger rules, and verification gates.
- `references/implementation-architecture.md`: config-driven implementation model, CLI contract, and lightweight validator scope.
- `references/module-architecture.md`: BlockSpec, renderer hub, theme/layout shell, document-set, and interaction module architecture.
- `references/project-profile.md`: repository-level `.cast-docs/` profile design for i18n, templates, writing rules, assets, and output paths.
- `references/interactive-features.md`: controlled progressive enhancements for diagrams.
- `references/document-types.md`: document types and required sections.
- `references/html-profile.md`: allowed HTML profile and safety rules.
- `references/component-library.md`: reusable document components.
- `references/writing-style.md`: writing and editing rules.
- `references/examples.md`: JSON fixtures and generated HTML examples.
- `assets/template-modules/`: shell template, base layout CSS, interaction scripts, and interaction hook HTML loaded by the renderer.
- `scripts/`: renderer, validators, template application, visual lint gates, document-set builder, and shared core helpers.

## Implementation Status

P0 generation is implemented:

- `scripts/validate_doc_json.py` validates document JSON against the configured document types, scenario skeletons, components, shell links, and typed block payloads.
- `scripts/render_html.py` renders document JSON to a self-contained HTML file with inline CSS and only the interaction modules needed by the document. It supports `--repo-root`, `--profile-dir`, and `--output-policy explicit|shareable|local` for profile-aware rendering.
- `scripts/validate_html.py` validates rendered HTML against `config/html-profile.json`.
- `scripts/validate_project_profile.py` validates `.cast-docs/` profile JSON, locales, paths, templates, and assets.
- `scripts/check_fixtures.py` validates fixture JSON, regenerated HTML, checked-in artifact freshness, and visual lint gates.
- `scripts/visual_lint.py` enforces lightweight visual gates for saturation, large-area colors, and fixed badge dimensions.
- `scripts/apply_template.py` applies explicit templates or profile-declared scenario templates to document JSON.
- `scripts/build_index.py` builds a document-set index and chapter pages from `cast-docs-set.json` or an explicit manifest path.

Document-set generation is implemented for static index pages and chapter pages with shared navigation and previous/next pagination.

Project Profile support is implemented for automatic CLI discovery, validation, default metadata/logo merging, profile-selected output paths, and template application.
