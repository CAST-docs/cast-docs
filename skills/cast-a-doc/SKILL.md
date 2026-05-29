---
name: cast-a-doc
description: Generate, validate, and render CAST Docs JSON into standardized self-contained HTML documents for engineering specs, plans, product requirements, decision records, and research notes. Use when the user wants a portable browser-viewable document, GitHub Pages friendly static docs, a controlled JSON-to-HTML documentation workflow, or validation of CAST Docs JSON/HTML/project-profile artifacts.
license: Apache-2.0
---

# cast-a-doc

`cast-a-doc` is the CAST Docs skill for casting notes, outlines, drafts, and instructions into stable, readable, self-contained HTML documents.

CAST Docs means Component Assembly Styled Templates.

Use this skill to produce, validate, and render stable self-contained HTML documents from CAST Docs JSON, notes, outlines, drafts, or instructions. The intended output is a static document, not a wiki product, CMS, web app, or collaborative editor.

## Invocation Rules

Invoke `cast-a-doc` when the user asks to:

- create, edit, validate, migrate, or review CAST Docs JSON
- render CAST Docs JSON into a single self-contained HTML document
- publish or refresh static documentation for GitHub Pages or a browser-viewable handoff
- validate generated CAST Docs HTML, project profiles, examples, fixtures, or skill bundle consistency
- apply CAST Docs templates or build a static CAST Docs document-set index

Do not invoke it for ordinary code implementation, broad project onboarding, planning-gate work, live wiki/CMS/web app development, general Markdown-only editing, or repository rewrite strategy. Use `cast-a-start` for project planning, TODO/CHANGELIST orchestration, readiness gates, and repository memory setup; use `cast-a-doc` once the task needs CAST Docs JSON, HTML rendering, or validation.

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

Prefer the JSON intermediate representation before HTML rendering. This keeps document structure deterministic and prevents formatting drift. Treat JSON validation as the first tool gate, not as a renderer side effect.

## Tool Routing

Use the stable script entrypoints as tools. Do not call internal `scripts/cast_docs_*.py` modules directly unless you are maintaining their implementation.

- JSON contract: `python3 scripts/validate_doc_json.py --input doc.json`
- Render: `python3 scripts/render_html.py --input doc.json --output doc.html --validate`
- HTML profile: `python3 scripts/validate_html.py --input doc.html`
- Project profile: `python3 scripts/validate_project_profile.py --repo-root .`
- Templates: `python3 scripts/apply_template.py --input draft.json --template .cast-docs/templates/plan.json --output doc.json --validate`
- Document sets: `python3 scripts/build_index.py --manifest docs/cast-docs/cast-docs-set.json --output docs/cast-docs/index.html --validate`
- Installed-skill maintainer gates: `scripts/visual_lint.py` and `scripts/check_fixtures.py`
- Repository checkout gates: `scripts/validate_schema_contract.py`, `scripts/validate_package_metadata.py`, and `scripts/validate_skill_bundle.py`

Read `references/tool-entrypoints.md` before choosing a command sequence beyond the basic JSON -> render -> HTML validation flow.

## JSON Contract

CAST Docs JSON is the source of truth. HTML is a generated artifact.

- `schemas/doc.schema.json` owns structural shape, required fields, primitive types, localized strings, and block payload object shapes.
- Python validators own semantic, safety, repository, and rendered-output rules.
- `scripts/validate_doc_json.py` is the daily JSON contract tool.
- `scripts/validate_schema_contract.py` is the repository checkout CI and maintainer drift guard.

Read `references/json-contract.md` before changing schema behavior, accepting generated JSON from another agent, or tightening validation rules.

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
- `references/tool-entrypoints.md`: public script entrypoints, command order, CI tools, and internal module boundaries.
- `references/json-contract.md`: schema, Python validator, drift guard, and compatibility boundaries for CAST Docs JSON.
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
