# Tool Entrypoints

`cast-a-doc` is one skill with several stable script entrypoints. Agents should call these scripts instead of importing internal `cast_docs_*` modules directly.

## Installed Skill Tools

Use these tools during normal authoring, rendering, and validation. They are included in the installed `cast-a-doc` skill bundle.

| Tool | Use When | Typical Command | Output |
| --- | --- | --- | --- |
| `scripts/validate_doc_json.py` | A CAST Docs JSON source is created, edited, migrated, or received from another agent. | `python3 scripts/validate_doc_json.py --input doc.json` | Pass/fail report for the JSON document contract. |
| `scripts/render_html.py` | A validated JSON document should become a self-contained HTML artifact. | `python3 scripts/render_html.py --input doc.json --output doc.html --validate` | Rendered HTML plus optional JSON and HTML validation. |
| `scripts/validate_html.py` | A generated HTML artifact must be checked independently. | `python3 scripts/validate_html.py --input doc.html` | Pass/fail report against `config/html-profile.json`. |
| `scripts/validate_project_profile.py` | A target repository contains `.cast-docs/` defaults or templates. | `python3 scripts/validate_project_profile.py --repo-root .` | Pass/fail report for project profile files and paths. |
| `scripts/apply_template.py` | A reusable template should shape an authoring draft. | `python3 scripts/apply_template.py --input draft.json --template .cast-docs/templates/plan.json --output doc.json --validate` | A composed document JSON source. |
| `scripts/build_index.py` | A document set needs an index page and chapter navigation. | `python3 scripts/build_index.py --manifest docs/cast-docs/cast-docs-set.json --output docs/cast-docs/index.html --validate` | Document-set index and chapter pages. |

## Installed Maintainer Tools

Use these tools for local fixture and visual checks. They are included in the installed skill bundle, but they are not required for every single document render.

| Tool | Use When | Typical Command | Output |
| --- | --- | --- | --- |
| `scripts/visual_lint.py` | Generated pages need lightweight visual safety checks. | `python3 scripts/visual_lint.py --input-dir examples --input index.html` | Pass/fail report for visual lint rules. |
| `scripts/check_fixtures.py` | Checked-in generated pages must stay fresh. | `python3 scripts/check_fixtures.py` | Pass/fail report for JSON, HTML, visual lint, and freshness. |
| `scripts/check_fixtures.py --update` | Source JSON changes intentionally require refreshed HTML artifacts. | `python3 scripts/check_fixtures.py --update` | Regenerated checked-in HTML artifacts. |

## Repository Checkout Tools

Use these only when working in the `CAST-docs/cast-a-doc` repository checkout. They are CI and release guards, not installed-skill authoring tools.

| Tool | Use When | Typical Command | Output |
| --- | --- | --- | --- |
| `scripts/validate_schema_contract.py` | Schema structure and validator assumptions must stay aligned. | `python3 scripts/validate_schema_contract.py` | Pass/fail report for schema contract invariants. |
| `scripts/validate_package_metadata.py` | Package metadata and version files change. | `python3 scripts/validate_package_metadata.py` | Pass/fail report for release metadata. |
| `scripts/validate_skill_bundle.py` | The installable skill bundle may have drifted from root files. | `python3 scripts/validate_skill_bundle.py` | Pass/fail report for bundled skill sync. |

## Standard Tool Order

For a single document:

```sh
python3 scripts/validate_doc_json.py --input doc.json
python3 scripts/render_html.py --input doc.json --output doc.html --validate
python3 scripts/validate_html.py --input doc.html
```

For a repository with a project profile:

```sh
python3 scripts/validate_project_profile.py --repo-root .
python3 scripts/validate_doc_json.py --input doc.json
python3 scripts/render_html.py --repo-root . --input doc.json --output doc.html --validate
python3 scripts/validate_html.py --input doc.html
```

For a repository checkout maintenance change:

```sh
python3 scripts/validate_project_profile.py --repo-root .
python3 scripts/validate_schema_contract.py
python3 scripts/validate_package_metadata.py
python3 scripts/validate_skill_bundle.py
python3 -m unittest discover -s tests
python3 scripts/visual_lint.py --input-dir examples --input-dir plan --input-dir spec --input index.html --input install.html --input readme.html --input todo.html --input changelist.html
python3 scripts/check_fixtures.py
```

## Internal Modules

The `scripts/cast_docs_*.py` modules are implementation boundaries, not public tool entrypoints. They may be read or patched during maintenance, but agents should not rely on them as stable command APIs.

Current internal modules include:

- `scripts/cast_docs_common.py`
- `scripts/cast_docs_context.py`
- `scripts/cast_docs_inline.py`
- `scripts/cast_docs_svg.py`
- `scripts/cast_docs_validation.py`
- `scripts/cast_docs_profile.py`
- `scripts/cast_docs_theme.py`
- `scripts/cast_docs_renderer_blocks.py`
- `scripts/cast_docs_renderer_diagrams.py`
- `scripts/cast_docs_renderer_shell.py`
- `scripts/cast_docs_html_profile.py`
- `scripts/cast_docs_cli.py`

`scripts/cast_docs_core.py` remains a compatibility facade for existing imports.
