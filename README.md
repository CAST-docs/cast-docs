# cast-a-doc

<img src="assets/cast-docs-logo.png" alt="CAST Docs logo" width="128">

`cast-a-doc` is a CAST Docs skill for turning notes, outlines, drafts, and instructions into structured engineering documents.

CAST Docs means **C**omponent **A**ssembly **S**tyled **T**emplates. In this repository, the skill casts source material into structured JSON and renders it as a self-contained HTML artifact. The JSON is the source; the HTML is what you share, publish, archive, or hand to another team.

## Install

Install or update the `cast-a-doc` Codex skill:

```bash
curl -fsSL https://cast-docs.github.io/cast-a-doc/install.sh | bash
```

Install `cast-a-doc` for Claude Code:

```bash
curl -fsSL https://cast-docs.github.io/cast-a-doc/install.sh | bash -s -- --claude
```

Install `cast-a-doc` for both agents:

```bash
curl -fsSL https://cast-docs.github.io/cast-a-doc/install.sh | bash -s -- --both
```

For options, safety checks, and local renderer setup, see the [install guide](https://cast-docs.github.io/cast-a-doc/install.html).

## Quick Start

Requires Python 3.9 or newer. `cast-a-doc` uses only the Python standard library.

```bash
git clone https://github.com/CAST-docs/cast-a-doc.git
cd cast-a-doc
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
python3 scripts/visual_lint.py --input-dir examples --input index.html --input install.html
python3 scripts/check_fixtures.py
```

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
- A designed repository-level `.cast-docs/` project profile for team templates, i18n, writing rules, reusable assets, and output defaults.
- `cast-a-doc` skill installation for Codex and Claude Code.

## Important Documents

- [index.html](index.html) / [Pages](https://cast-docs.github.io/cast-a-doc/) - skill overview, examples, and design rationale.
- [install.html](install.html) / [Pages](https://cast-docs.github.io/cast-a-doc/install.html) - one-line install commands, environment overrides, and troubleshooting.
- [examples/component-gallery.html](examples/component-gallery.html) / [Pages](https://cast-docs.github.io/cast-a-doc/examples/component-gallery.html) - visual reference for common blocks and inline marks.
- [INSTALL_AGENT.md](INSTALL_AGENT.md) - compact copy-ready install handoff for coding agents.
- [SKILL.md](SKILL.md) - agent skill manifest and loading instructions.
- [references/project-profile.md](references/project-profile.md) - `.cast-docs/` project profile design for repository-specific defaults.

## Authoring Model

1. Choose a document type and scenario skeleton.
2. Read `.cast-docs/` project profile defaults when the target repository provides them.
3. Produce JSON that matches the schema and manifest contract.
4. Run `render_html.py --validate`.
5. Share the generated HTML as the artifact.

The renderer intentionally avoids external scripts, CDNs, and viewer-specific Markdown extensions. Output should work from a browser, email attachment, S3 bucket, or GitHub Pages.

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
python3 scripts/check_fixtures.py --update
```

## License

`cast-a-doc` is licensed under the [Apache License 2.0](LICENSE), except as noted in [NOTICE](NOTICE).

The CAST Docs name, logo, and other project branding assets are not licensed for use in modified versions, derived products, or services without prior written permission. Truthful references to CAST Docs for origin or compatibility are allowed.
