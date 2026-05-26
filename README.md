# CAST Docs

**C**omponent **A**ssembly **S**tyled **T**emplates.

A small static document rendering system. Write engineering documents as JSON, get back a single self-contained HTML file that you can open in Chrome, attach to an email, archive, or publish to GitHub Pages.

```bash
python3 scripts/render_html.py \
  --input examples/problem-investigation.json \
  --output out.html \
  --validate
```

Treat the rendered HTML as the artifact. Treat the JSON as the source.

## What this is for

CAST Docs is a controlled replacement for Markdown-based technical documents:

- Engineering specs and plans
- Product requirements
- Decision records
- Research notes
- Cross-team alignment write-ups, problem investigations, document digests, principle showcases

The intended user writes in JSON — or asks Claude to convert prose to JSON — then validates and renders. The output is a stable, readable static document, not a wiki page, not a CMS entry, not a collaborative editor surface.

## What it does

- Renders structured JSON into one self-contained HTML file. CSS is inlined. No external CSS, JS, fonts, CDN, or images.
- Enforces one visual system and one class vocabulary across every generated document.
- Composes documents from typed blocks (`paragraph`, `callout`, `list`, `code`, `table`, `diagram`, `diff`, `details`, `quote`, and friends) selected per scenario.
- Validates the JSON against a schema and the configured registries for document types, scenarios, and components.
- Validates the rendered HTML against an allow-listed tag, attribute, and URL profile.
- Injects renderer-owned progressive enhancements (currently: a diagram viewer with zoom, pan, SVG / PNG download) only when the layout and content actually require them.

## What it doesn't do

These are intentional non-goals:

- **No editor and no UI.** Authoring happens in JSON or upstream prose. No WYSIWYG, no inline edit, no live preview.
- **No runtime services.** No server, database, auth, search index, or page builder.
- **No user-authored JavaScript.** Only renderer-owned scripts for the interaction modules declared in `config/interactions.json` are allowed in output.
- **No external assets.** No CDN fonts, remote images, analytics, or script tags pointing at the network.
- **No multi-page document sets yet.** `single-doc` is implemented; `document-set` is declared in config but its shell, navigation model, and index builder are not.
- **No live collaboration.** Versioning lives in git, like the rest of the codebase.

## Why this shape

- **HTML instead of Markdown.** Markdown cannot carry the visual vocabulary this system depends on — callouts, decision matrices, diff blocks, diagram viewers, controlled tables — without per-renderer extensions. Owning the HTML produces consistent output across viewers.
- **JSON intermediate.** Prose-to-HTML by a model is non-deterministic. Prose → JSON → HTML separates content from rendering, makes the JSON validatable and diffable, and lets the renderer produce byte-stable output.
- **Single inline-CSS file.** The output should open in any browser, attach to email, sit on GitHub Pages, and survive being copied to S3. Self-contained is the only property that holds across those surfaces.
- **Config-driven renderer.** Adding a new component, theme, layout, or interaction is config plus an asset file, not a Python branch. Visual and structural rules live in `config/`. The Python in `scripts/` only assembles.

The influences are intentional: simplicity and readability from BookStack, GitHub-Pages-friendly publishing from Wiki.js, reusable document blocks from Docmost, JSON-schema discipline from Tiptap / ProseMirror. None of those products' scope is borrowed.

## Quick start

Requires Python 3.9+. Standard library only — no `pip install` step.

Render one of the bundled examples:

```bash
python3 scripts/render_html.py \
  --input examples/problem-investigation.json \
  --output out.html \
  --validate
```

The `--validate` flag runs the JSON schema check before rendering and the HTML profile check after.

The validators can also run on their own:

```bash
python3 scripts/validate_doc_json.py --input examples/option-decision.json
python3 scripts/validate_html.py     --input out.html
```

## Install

### As a Claude Code skill

Clone the repository into your Claude Code skills directory:

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/jinhuang712/cast-docs.git ~/.claude/skills/cast-docs
```

The skill registers as `cast-docs` and activates when you ask Claude for a self-contained HTML document, an engineering spec, a decision record, and similar requests. The skill manifest is `SKILL.md`; the references in `references/` are loaded on demand.

### As a local renderer

```bash
git clone https://github.com/jinhuang712/cast-docs.git
cd cast-docs
python3 scripts/render_html.py \
  --input examples/problem-investigation.json \
  --output out.html \
  --validate
```

No third-party dependencies. If `python3 --version` reports 3.9 or newer, it runs.

## Repository layout

```text
config/                       configuration registries (themes, layouts, components, interactions, scenarios, document types, HTML profile)
schemas/                      doc.schema.json — the JSON contract
assets/template-modules/      shell HTML, base CSS, interaction scripts, interaction hook HTML
examples/                     JSON fixtures and rendered HTML samples
scripts/                      render_html.py, validate_doc_json.py, validate_html.py, cast_docs_core.py
references/                   design laws, generation contract, module architecture, etc.
SKILL.md                      Claude skill manifest
```

## Document types and scenarios

Five document types (`config/document-types.json`):

`engineering-spec`, `engineering-plan`, `product-requirement`, `decision-record`, `research-note`.

Five scenario skeletons (`config/scenario-skeletons.json`), each with a JSON fixture and a pre-rendered HTML preview in `examples/`:

| Skeleton | Use when | Source | Preview |
|---|---|---|---|
| `problem-investigation` | tracking down a bug, regression, or anomaly | [JSON](examples/problem-investigation.json) | [HTML](https://htmlpreview.github.io/?https://github.com/jinhuang712/cast-docs/blob/main/examples/problem-investigation.html) |
| `option-decision`       | comparing options and recording why one was chosen | [JSON](examples/option-decision.json) | [HTML](https://htmlpreview.github.io/?https://github.com/jinhuang712/cast-docs/blob/main/examples/option-decision.html) |
| `cross-team-alignment`  | aligning multiple teams on scope and ownership | [JSON](examples/cross-team-alignment.json) | [HTML](https://htmlpreview.github.io/?https://github.com/jinhuang712/cast-docs/blob/main/examples/cross-team-alignment.html) |
| `document-digest`       | summarizing a long document or set of documents | [JSON](examples/document-digest.json) | [HTML](https://htmlpreview.github.io/?https://github.com/jinhuang712/cast-docs/blob/main/examples/document-digest.html) |
| `principle-showcase`    | curating principles or guidelines for reuse | [JSON](examples/principle-showcase.json) | [HTML](https://htmlpreview.github.io/?https://github.com/jinhuang712/cast-docs/blob/main/examples/principle-showcase.html) |

Preview links route through [htmlpreview.github.io](https://htmlpreview.github.io/) because GitHub serves raw HTML as source. Clone the repository and open the file in a browser for a faster, third-party-free view.

## Validation pipeline

```text
JSON  →  validate_doc_json  →  render_html  →  validate_html  →  HTML
```

Each stage runs independently. `render_html.py --validate` runs all three end-to-end.

The validators are deliberately strict: an unknown block type, an unregistered component, a disallowed URL scheme, or a placeholder that survived rendering all fail loudly.

## Status

**Done (P0)**

- `single-doc` rendering with the full block library and interaction injection.
- `cast-default` theme compiled from `config/theme-tokens.json`.
- `diagram-viewer` interaction (lightbox, zoom, pan, SVG / PNG download).
- JSON validation and HTML profile validation.

**Planned**

- `shell.document-set.html` and the `document-set` layout (sidebar, topbar, pagination).
- `scripts/build_index.py` for GitHub-Pages-friendly index pages.
- Typography and spacing tokens compiled into the base CSS — currently only color tokens are.
- Renderer-generated example HTML to replace any remaining hand-authored samples.

See `references/module-architecture.md` for the longer architecture notes.

## License

Not yet declared. Treat the repository as source-available for personal evaluation until a `LICENSE` file is added.
