# CAST Docs

<img src="assets/cast-docs-logo.png" alt="CAST Docs logo" width="128">

**C**omponent **A**ssembly **S**tyled **T**emplates — render engineering documents from JSON to self-contained HTML.

```bash
python3 scripts/render_html.py \
  --input examples/problem-investigation.json \
  --output out.html \
  --validate
```

Treat the rendered HTML as the artifact. Treat the JSON as the source.

## Quick start

Requires Python 3.9+. Standard library only — no `pip install` step.

```bash
python3 scripts/render_html.py \
  --input examples/problem-investigation.json \
  --output out.html \
  --validate
```

The `--validate` flag runs the JSON schema check before rendering and the HTML profile check after. The validators can also run on their own:

```bash
python3 scripts/validate_doc_json.py --input examples/option-decision.json
python3 scripts/validate_html.py     --input out.html
```

## Install

### As a Claude Code skill

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/CAST-docs/cast-docs.git ~/.claude/skills/cast-docs
```

The skill registers as `cast-docs` and activates when you ask Claude for a self-contained HTML document, an engineering spec, a decision record, and similar requests. The skill manifest is `SKILL.md`; the references in `references/` are loaded on demand.

### As a local renderer

```bash
git clone https://github.com/CAST-docs/cast-docs.git
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
assets/cast-docs-logo.png     project logo used by README and rendered document chrome
examples/                     JSON fixtures and rendered HTML samples
site/                         landing-page source (rendered to index.html)
scripts/                      render_html.py, validate_doc_json.py, validate_html.py, cast_docs_core.py
references/                   design laws, generation contract, module architecture, etc.
SKILL.md                      Claude skill manifest
```

To re-render the landing after editing `site/landing.json`:

```bash
python3 scripts/render_html.py --input site/landing.json --output index.html --validate
```

Documents can opt into logo chrome through `metadata.logo`. Local image paths are resolved from the repository root and embedded as data URIs during render, so the output HTML remains self-contained:

```json
{
  "metadata": {
    "logo": {
      "src": "assets/cast-docs-logo.png",
      "alt": "CAST Docs logo",
      "href": "index.html"
    }
  }
}
```

---

**Scenario previews, design rationale, and project status → [cast-docs.github.io/cast-docs](https://cast-docs.github.io/cast-docs/)**

## License

Not yet declared. Treat the repository as source-available for personal evaluation until a `LICENSE` file is added.
