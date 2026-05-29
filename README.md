# cast-a-doc

<img src="assets/cast-docs-logo.png" alt="CAST Docs logo" width="128">

`cast-a-doc` is a CAST Docs skill for turning notes, outlines, drafts, and instructions into structured engineering documents.

CAST Docs means **C**omponent **A**ssembly **S**tyled **T**emplates. In this repository, the skill casts source material into structured JSON and renders it as a self-contained HTML artifact. The JSON is the source; the HTML is what you share, publish, archive, or hand to another team.

## Install

Inspect the skill, then install or update the `cast-a-doc` Codex skill with GitHub CLI pinned to a release tag:

```bash
gh skill preview CAST-docs/cast-a-doc cast-a-doc --pin v0.1.0
```

```bash
gh skill install CAST-docs/cast-a-doc cast-a-doc --pin v0.1.0 --agent codex --scope user
```

Install `cast-a-doc` for Claude Code:

```bash
gh skill install CAST-docs/cast-a-doc cast-a-doc --pin v0.1.0 --agent claude-code --scope user
```

Install `cast-a-doc` for both agents:

```bash
curl -fsSL https://cast-docs.github.io/cast-a-doc/install.sh | bash -s -- --both
```

The compatibility installer delegates to `gh skill install`; it no longer clones the repository into an agent directory. For stricter environments, download `install.sh`, review it locally, then run `bash install.sh --pin v0.1.0 --both`. For options, safety checks, and local renderer setup, see the [install guide](https://cast-docs.github.io/cast-a-doc/install.html).

## Quick Start

Requires Python 3.9 or newer. `cast-a-doc` uses only the Python standard library.

```bash
rm -rf /tmp/cast-a-doc-skill
gh skill install CAST-docs/cast-a-doc cast-a-doc --pin v0.1.0 --dir /tmp/cast-a-doc-skill --force
cd /tmp/cast-a-doc-skill/cast-a-doc
scripts/render_example.sh examples/problem-investigation.json out.html
```

Validate JSON and generated HTML explicitly:

```bash
python3 scripts/validate_doc_json.py --input examples/option-decision.json
python3 scripts/render_html.py --input examples/option-decision.json --output out.html --validate
python3 scripts/validate_html.py --input out.html
```

Validate project profile defaults and checked-in fixtures:

```bash
python3 scripts/validate_project_profile.py --repo-root .
python3 scripts/validate_schema_contract.py
python3 scripts/validate_package_metadata.py
python3 -m unittest discover -s tests
python3 scripts/visual_lint.py --input-dir examples --input-dir plan --input-dir spec --input index.html --input install.html --input readme.html --input todo.html --input changelist.html
python3 scripts/check_fixtures.py
```

## Packaging And Releases

The repository remains script-first: existing commands under `scripts/` are the supported local entry points and do not require installation. `pyproject.toml` adds lightweight package metadata without changing the CLI surface.

Release versions are recorded in `VERSION`; Git tags use the matching `v<version>` form. Use [RELEASE.md](RELEASE.md) before tagging to run validation, refresh generated pages, and verify pinned install commands.

## What It Provides

- A JSON document contract in `schemas/doc.schema.json`.
- A deterministic renderer in `scripts/render_html.py`.
- Validation for source JSON and generated HTML.
- Project profile discovery, validation, and profile-selected output paths.
- Project template application for authoring-time JSON composition.
- Document-set index and chapter page generation with shared navigation and pagination.
- Built-in scenario skeletons for investigations, decisions, digests, cross-team alignment, and principle showcases.
- Reusable document components such as summaries, callouts, tables, diagrams, diff blocks, action cards, source references, and code blocks.
- Self-contained HTML with inline CSS and renderer-owned interactions such as code copy, language switching, and diagram controls.
- Language switching can prompt readers to save a CAST Docs global default language preference in browser storage.
- A designed repository-level `.cast-docs/` project profile for team templates, i18n, writing rules, reusable assets, style profiles, and output defaults.
- `cast-a-doc` skill installation for Codex and Claude Code.

## Important Documents

- [index.html](index.html) / [Pages](https://cast-docs.github.io/cast-a-doc/) - skill overview, examples, and design rationale.
- [install.html](install.html) / [Pages](https://cast-docs.github.io/cast-a-doc/install.html) - one-line install commands, environment overrides, and troubleshooting.
- [readme.html](readme.html) / [Pages](https://cast-docs.github.io/cast-a-doc/readme.html) - CAST Docs HTML view of this repository overview.
- [examples/component-gallery.html](examples/component-gallery.html) / [Pages](https://cast-docs.github.io/cast-a-doc/examples/component-gallery.html) - visual reference for common blocks and inline marks.
- [INSTALL_AGENT.md](INSTALL_AGENT.md) - compact copy-ready install handoff for coding agents.
- [skills/cast-a-doc/SKILL.md](skills/cast-a-doc/SKILL.md) - agent skill manifest and loading instructions.
- [plan/index.html](plan/index.html) / [Pages](https://cast-docs.github.io/cast-a-doc/plan/) - product plan produced through `cast-a-start` guided migration.
- [spec/index.html](spec/index.html) / [Pages](https://cast-docs.github.io/cast-a-doc/spec/) - technical spec produced through `cast-a-start` guided migration.
- [todo.html](todo.html) / [site/todo.json](site/todo.json) - project-level uncertainty and deferred work.
- [changelist.html](changelist.html) / [site/changelist.json](site/changelist.json) - planning and documentation change history.
- [references/project-profile.md](references/project-profile.md) - `.cast-docs/` project profile design for repository-specific defaults.

## Authoring Model

1. Choose a document type and scenario skeleton.
2. Read `.cast-docs/` project profile defaults when the target repository provides them.
3. Produce JSON that matches the schema and manifest contract.
4. Run `render_html.py --validate`.
5. Share the generated HTML as the artifact.

The renderer intentionally avoids external scripts, CDNs, and viewer-specific Markdown extensions. Output should work from a browser, email attachment, S3 bucket, or GitHub Pages.

`schemas/doc.schema.json` is the structural JSON contract: fields, required properties, enum values, and object shapes. The Python validators enforce semantic and safety rules that JSON Schema cannot express cleanly here, including project profile consistency, safe URLs and media paths, raw SVG sanitization, HTML profile compliance, visual lint, and rendered fixture freshness.

When a user does not provide an output path, skill-driven generation should use the repository profile default if one exists. Otherwise it should ask whether the output is a shareable document under `docs/cast-docs/` or a local draft under `.cast-docs/out/`.

Apply a template and build a document-set from a manifest:

```bash
python3 scripts/apply_template.py --input draft.json --template .cast-docs/templates/plan.json --output doc.json --validate
python3 scripts/build_index.py --manifest docs/cast-docs/cast-docs-set.json --output docs/cast-docs/index.html --validate
```

## Regenerate Pages

```bash
python3 scripts/render_html.py --input site/landing.json --output index.html --validate
python3 scripts/render_html.py --input site/install.json --output install.html --validate
python3 scripts/render_html.py --input site/readme.json --output readme.html --validate
python3 scripts/render_html.py --input site/todo.json --output todo.html --validate
python3 scripts/render_html.py --input site/changelist.json --output changelist.html --validate
python3 scripts/render_html.py --repo-root . --input plan/index.json --output plan/index.html --validate
python3 scripts/render_html.py --repo-root . --input plan/00_overview.json --output plan/00_overview.html --validate
python3 scripts/render_html.py --repo-root . --input plan/01_features.json --output plan/01_features.html --validate
python3 scripts/render_html.py --repo-root . --input plan/02_interaction.json --output plan/02_interaction.html --validate
python3 scripts/render_html.py --repo-root . --input spec/index.json --output spec/index.html --validate
python3 scripts/render_html.py --repo-root . --input spec/00_architecture.json --output spec/00_architecture.html --validate
python3 scripts/render_html.py --repo-root . --input spec/01_document_model.json --output spec/01_document_model.html --validate
python3 scripts/render_html.py --repo-root . --input spec/02_verification.json --output spec/02_verification.html --validate
python3 scripts/render_html.py --repo-root . --input spec/decisions.json --output spec/decisions.html --validate
python3 scripts/check_fixtures.py --update
```

## License

`cast-a-doc` is licensed under the [Apache License 2.0](LICENSE), except as noted in [NOTICE](NOTICE).

The CAST Docs name, logo, and other project branding assets are not licensed for use in modified versions, derived products, or services without prior written permission. Truthful references to CAST Docs for origin or compatibility are allowed.
