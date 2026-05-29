# Module Architecture

`cast-a-doc` is a small static document rendering skill in the CAST Docs system. It should feel like a restrained document product, while keeping the final artifact self-contained and easy to validate.

## Architecture Shape

```text
Built-in Registries + optional .cast-docs Project Profile
  -> Profile Resolver
Document JSON
  -> Manifest Resolver
  -> Block Registry
  -> Renderer Hub
  -> Theme + Layout Resolver
  -> Shell Composer
  -> Interaction Injector
  -> HTML Profile Validator
  -> Self-contained HTML
```

The important boundary: generated content describes structure and intent. Renderer modules own HTML assembly, styling, and approved interactions.

## Module Types

### Document Schema

Owns the JSON contract:

- Metadata.
- Manifest.
- Sections.
- Typed blocks.
- Structured diagram source with controlled SVG fallback.

Source files:

- `schemas/doc.schema.json`
- `config/document-types.json`
- `config/scenario-skeletons.json`

### Project Profile

Owns repository-specific defaults stored in `.cast-docs/`.

Source files:

- `.cast-docs/project.json`
- `.cast-docs/preferences.json`
- `.cast-docs/i18n.json`
- `.cast-docs/glossary.json`
- `.cast-docs/writing-style.md`
- `.cast-docs/templates/`
- `.cast-docs/examples/`
- `.cast-docs/assets/`

The profile resolver merges built-in defaults, repository profile values, and current request choices. It should not mutate `.cast-docs/` while generating a document. Profile changes require explicit user intent.

Implementation note: `scripts/cast_docs_core.py` is now a compatibility facade. Shared path, JSON loading, escaping, and dataclass helpers live in `scripts/cast_docs_common.py`; renderer state and i18n helpers live in `scripts/cast_docs_context.py`; inline text handling lives in `scripts/cast_docs_inline.py`; SVG sanitization lives in `scripts/cast_docs_svg.py`; document validation lives in `scripts/cast_docs_validation.py`; project profile handling lives in `scripts/cast_docs_profile.py`; theme handling lives in `scripts/cast_docs_theme.py`; block, diagram, and shell rendering live in `scripts/cast_docs_renderer_blocks.py`, `scripts/cast_docs_renderer_diagrams.py`, and `scripts/cast_docs_renderer_shell.py`; HTML profile validation lives in `scripts/cast_docs_html_profile.py`; CLI helpers live in `scripts/cast_docs_cli.py`.

### BlockSpec

Each block should eventually be described as a BlockSpec.

```json
{
  "type": "callout",
  "schemaRef": "#/$defs/calloutBlock",
  "renderer": "callout",
  "allowedChildren": ["paragraph", "list", "code"],
  "classes": ["callout", "callout-info", "callout-warning"],
  "interactions": [],
  "validation": ["variant-known", "body-non-empty"],
  "examples": ["examples/problem-investigation.json#root-cause"]
}
```

This mirrors the useful part of Lark/Docmost: every module has schema, renderer, attributes, and serialization rules.

### Renderer Hub

The renderer hub maps `block.type` to rendering functions. It should avoid scenario-specific branches.

```text
paragraph -> renderParagraph
callout   -> renderCallout
table     -> renderTable
diagram   -> renderDiagram
diff      -> renderDiff
```

Scenarios affect which sections and components are selected. They should not change how a block renders.

### Theme Tokens

Theme tokens carry the restrained visual system. They should compile into CSS custom properties.

Source file:

- `config/theme-tokens.json`

Design rules:

- One primary color.
- One accent color.
- Neutral surfaces first.
- Semantic state colors for info/success/warning/danger.
- 4px spacing rhythm.
- 4-10px regular radii.
- No decorative gradients or one-off palettes.

### Layout Shells

Layout shells control document chrome.

Source file:

- `config/layouts.json`

Supported shells:

- `single-doc`: one standalone HTML file with a fixed left-rail table of contents and a top bar.
- `document-set`: a static documentation set with index, a persistent sidebar shared across files, topbar breadcrumbs, and previous/next pagination.

The final output may still be self-contained per file. `document-set` means a group of self-contained HTML files that share the same generated navigation model.

Shells may expose optional link slots, such as `topbar-links`, for caller-provided jumps back to an index page, repository home, or parent document. Empty slots must not render visible chrome. These links are document navigation, not implementation metadata.

### Interaction Modules

Interactions are renderer-owned progressive enhancements. They are injected only when selected by layout or manifest.

Source file:

- `config/interactions.json`

Examples:

- `diagram-viewer`: lightbox, zoom, pan, SVG download, PNG download.
- `finder-open`: local folder opening through installer-managed URL scheme.
- `copy-code`: copy code or prompt blocks.
- `toc-scrollspy`: active heading highlight in long document-set pages.
- `slider-control`: range input with renderer-owned value updates and preview effects.

Generated content must not author scripts. It may only provide semantic hooks such as `data-interaction`, `data-download-name`, or `data-component`.

### Shell Composer

The shell composer combines:

- Layout shell.
- Optional shell links from `metadata.shellLinks`.
- Optional logo and reusable media from `.cast-docs/assets/`.
- Theme CSS variables.
- Component CSS.
- Rendered sections.
- Selected interaction modules.
- Footer metadata.

The composer should be the only place where the final one-file HTML is assembled.

### Validator

Validation should remain layered:

1. `schema`: JSON shape is valid.
2. `manifest`: selected document type, scenario, sections, and components are valid.
3. `profile`: repository profile files are valid, declared paths stay inside the repository, and referenced assets exist.
4. `render`: every block type has a renderer and every required section is present.
5. `html-profile`: allowed tags, attributes, classes, URL schemes, and renderer-owned scripts.
6. `output`: no unresolved placeholders, TOC links resolve, interaction hooks match injected modules.

## Document Set Model

`document-set` is the main lesson from Jsonita. A set manifest should define navigation once:

```json
{
  "id": "architecture-pack",
  "title": "Architecture Pack",
  "sections": [
    {
      "id": "plan",
      "label": "Plan",
      "chapters": [
        {
          "id": "overview",
          "number": "00",
          "title": "Overview",
          "href": "plan/00_overview.html",
          "source": "examples/overview.json"
        }
      ]
    }
  ]
}
```

Renderer behavior:

- Generate `index.html`.
- Generate each chapter HTML.
- Inject the same sidebar/topbar/pagination model into each chapter.
- Keep every generated HTML openable by itself.
- Avoid runtime navigation generation unless an interaction module explicitly needs it.

## Serialization Rules

Borrow the Docmost idea of semantic serialization, not its full editor stack.

Recommended HTML attributes:

- `data-component="<component-id>"`
- `data-block-type="<block-type>"`
- `data-section-id="<section-id>"`
- `data-interaction="<interaction-id>"`
- `data-download-name="<safe-name>"`

These attributes make output inspectable and validateable without tying CAST Docs to a browser editor.

## Source Layout

```text
config/
  document-types.json
  scenario-skeletons.json
  components.json
  html-profile.json
  interactions.json
  layouts.json
  theme-tokens.json
schemas/
  doc.schema.json
assets/
  template-modules/
    shell.single.html
    styles.base.css
    interactions.diagram-viewer.js
    interactions.slider-control.js
    hooks.diagram-viewer.html
scripts/
  cast_docs_core.py
  render_html.py
  validate_doc_json.py
  validate_html.py
  build_index.py
.cast-docs/
  project.json
  preferences.json
  i18n.json
  glossary.json
  writing-style.md
  templates/
  examples/
  assets/
  out/
```

The renderer loads `shell.<layout>.html` and substitutes named slots. Interaction hook HTML and scripts are loaded by file-naming convention (`hooks.<id>.html`, `interactions.<id>.js`) so adding a new interaction is config plus assets, not Python branches. The final generated artifact remains a complete HTML file.

## Implementation Status

Done:

1. Render `single-doc` from document JSON using `assets/template-modules/shell.single.html`.
2. Compile `config/theme-tokens.json` into the `:root` CSS variables; static layout CSS lives in `assets/template-modules/styles.base.css`.
3. Map `block.type` to renderer functions through a registry built from `config/components.json`.
4. Inject interaction hooks and scripts only when the selected layout and document content trigger them.
5. Discover and validate `.cast-docs/` project profiles for CLI rendering.
6. Select profile-controlled output paths for shareable and local draft artifacts.
7. Check fixture JSON, regenerated HTML, and committed artifact freshness.
8. Build document-set index and chapter pages from `cast-docs-set.json` manifests.
9. Add shared document-set navigation and previous/next pagination.
10. Apply explicit or profile-declared templates during authoring.
11. Run visual lint gates for saturation, fixed badge dimensions, and large color areas.
12. Extract typography / spacing / radius / motion tokens into CSS variables consumed by `styles.base.css`.
