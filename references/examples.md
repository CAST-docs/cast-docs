# Examples

CAST Docs keeps compact JSON fixtures under `examples/`. Each configured scenario skeleton should have at least one fixture.

Current fixtures:

- `examples/problem-investigation.json`
- `examples/cross-team-alignment.json`
- `examples/option-decision.json`
- `examples/document-digest.json`
- `examples/principle-showcase.json`

Current HTML examples:

- `examples/problem-investigation.html`
- `examples/principle-showcase.html`
- `examples/cast-docs-sample.html`

Each fixture should include:

- Metadata.
- Manifest with document type, scenario, selected sections, and component selection.
- Sections using typed blocks from `schemas/doc.schema.json`.
- At least one meaningful component trigger when the scenario calls for it.

Fixtures should stay small enough to inspect quickly. They are contract tests for the renderer and validator.

The renderer can generate fresh HTML from every JSON fixture:

```sh
python3 scripts/render_html.py --input examples/problem-investigation.json --output dist/problem-investigation.html --validate
```

Hand-authored HTML examples remain visual references; generated HTML is the validation target for the renderer.
