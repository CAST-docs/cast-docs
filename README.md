# CAST Docs

<img src="assets/cast-docs-logo.png" alt="CAST Docs logo" width="128">

**C**omponent **A**ssembly **S**tyled **T**emplates - a controlled renderer for engineering documents.

CAST Docs turns structured JSON into a self-contained HTML artifact. The JSON is the source, the HTML is what you share, publish, archive, or hand to another team.

## Install

Install or update the Codex skill:

```bash
curl -fsSL https://cast-docs.github.io/cast-docs/install.sh | bash
```

Install for Claude Code:

```bash
curl -fsSL https://cast-docs.github.io/cast-docs/install.sh | bash -s -- --claude
```

Install both agent skills:

```bash
curl -fsSL https://cast-docs.github.io/cast-docs/install.sh | bash -s -- --both
```

For options, safety checks, and local renderer setup, see the [install guide](https://cast-docs.github.io/cast-docs/install.html).

## Quick Start

Requires Python 3.9 or newer. CAST Docs uses only the Python standard library.

```bash
git clone https://github.com/CAST-docs/cast-docs.git
cd cast-docs
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
python3 scripts/check_fixtures.py
```

## What It Provides

- A JSON document contract in `schemas/doc.schema.json`.
- A deterministic renderer in `scripts/render_html.py`.
- Validation for source JSON and generated HTML.
- Project profile discovery, validation, and profile-selected output paths.
- Built-in scenario skeletons for investigations, decisions, digests, cross-team alignment, and principle showcases.
- Reusable document components such as summaries, callouts, tables, diagrams, diff blocks, action cards, source references, and code blocks.
- Self-contained HTML with inline CSS and renderer-owned interactions such as code copy, language switching, and diagram controls.
- A designed repository-level `.cast-docs/` project profile for team templates, i18n, writing rules, reusable assets, and output defaults.
- Agent skill installation for Codex and Claude Code.

## Important Documents

- [index.html](index.html) / [Pages](https://cast-docs.github.io/cast-docs/) - project overview, examples, and design rationale.
- [install.html](install.html) / [Pages](https://cast-docs.github.io/cast-docs/install.html) - one-line install commands, environment overrides, and troubleshooting.
- [examples/component-gallery.html](examples/component-gallery.html) / [Pages](https://cast-docs.github.io/cast-docs/examples/component-gallery.html) - visual reference for common blocks and inline marks.
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

Build a document-set index from a manifest:

```bash
python3 scripts/build_index.py --manifest docs/cast-docs/cast-docs-set.json --output docs/cast-docs/index.html --validate
```

## Repository Layout

```text
assets/                       shared template modules, CSS, interaction scripts, and logo assets
config/                       component, theme, layout, interaction, scenario, document type, and HTML profile registries
examples/                     JSON fixtures and rendered HTML examples
references/                   design laws, generation contract, module architecture, and writing guidance
references/project-profile.md repository-level .cast-docs profile design
schemas/doc.schema.json       JSON contract for source documents
scripts/cast_docs_core.py     shared renderer and validator implementation
scripts/render_html.py        render JSON to self-contained HTML
scripts/validate_doc_json.py  validate source JSON
scripts/validate_html.py      validate rendered HTML against the controlled HTML profile
scripts/validate_project_profile.py validate repository .cast-docs profile defaults
scripts/check_fixtures.py      validate fixture JSON, generated HTML, and artifact freshness
scripts/build_index.py        build a document-set index from cast-docs-set.json
scripts/render_example.sh     render one bundled example with validation
scripts/install_codex_skill.sh install or update the Codex skill from a local checkout
scripts/install_claude_skill.sh install or update the Claude Code skill from a local checkout
install.sh                    GitHub Pages one-line skill installer
site/landing.json             source for index.html
site/install.json             source for install.html
index.html                    rendered project site
install.html                  rendered installation guide
INSTALL_AGENT.md              copy-ready install commands for coding agents
SKILL.md                      agent skill manifest
```

## Regenerate Pages

```bash
python3 scripts/render_html.py --input site/landing.json --output index.html --validate
python3 scripts/render_html.py --input site/install.json --output install.html --validate
python3 scripts/check_fixtures.py --update
```

## License

Not yet declared. Treat the repository as source-available for personal evaluation until a `LICENSE` file is added.
