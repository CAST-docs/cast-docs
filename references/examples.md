# Examples

`cast-a-doc` keeps compact JSON fixtures under `examples/`. Each configured scenario skeleton should have at least one fixture.

Current fixtures:

- `examples/problem-investigation.json`
- `examples/cross-team-alignment.json`
- `examples/option-decision.json`
- `examples/document-digest.json`
- `examples/principle-showcase.json`
- `examples/bilingual-decision.json`
- `examples/component-gallery.json`

Current rendered HTML previews (regenerated from the JSON fixtures above):

- `examples/problem-investigation.html`
- `examples/cross-team-alignment.html`
- `examples/option-decision.html`
- `examples/document-digest.html`
- `examples/principle-showcase.html`
- `examples/bilingual-decision.html`
- `examples/component-gallery.html`

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

All HTML examples are renderer-generated and serve as both visual references and validation targets.

## Project Profile Examples

Repository-specific examples should live under `.cast-docs/examples/` in the target repository. Use them for known-good local conventions, such as a team incident report, a product requirement shape, or a bilingual decision record.

Rules:

- Keep repository examples sanitized.
- Keep them small enough to review.
- Use only supported document types, scenarios, and components.
- Put reusable logos, screenshots, and icons under `.cast-docs/assets/` and reference them through approved fields.
- Do not treat `.cast-docs/examples/` as generated output; local drafts belong in `.cast-docs/out/`.
