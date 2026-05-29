# JSON Contract

CAST Docs JSON is the source of truth for `cast-a-doc`. HTML is a rendered artifact. Treat the JSON contract as the first tool boundary in every authoring or migration workflow.

## Contract Sources

- `schemas/doc.schema.json` is the machine-readable structural contract.
- `references/generation-contract.md` explains generation-time manifest and template boundaries.
- `references/document-types.md` explains supported document types and required sections.
- `references/component-library.md` explains reusable block intent and expected payloads.
- `examples/*.json`, `site/*.json`, `plan/*.json`, and `spec/*.json` are executable examples.
- `scripts/validate_doc_json.py` is the daily JSON contract tool.
- `scripts/validate_schema_contract.py` is the repository checkout CI and maintainer drift guard.

## Required Workflow

Any task that creates, edits, migrates, or accepts CAST Docs JSON must run the JSON validator before rendering:

```sh
python3 scripts/validate_doc_json.py --input doc.json
python3 scripts/render_html.py --input doc.json --output doc.html --validate
python3 scripts/validate_html.py --input doc.html
```

`render_html.py --validate` is useful, but it does not replace the explicit JSON contract step when reviewing or handing off a JSON source.

## Schema Boundary

`schemas/doc.schema.json` owns structural rules:

- top-level `metadata`, `manifest`, and `sections`
- required fields and primitive types
- localized string shapes
- known block variants and payload object shapes
- enum-like values that are stable enough to keep in schema

Add a rule to the schema when it changes the authoring shape or prevents invalid JSON from being emitted by generators.

## Python Validator Boundary

Python validators own semantic, safety, repository, and rendered-output rules:

- document type, scenario, component, theme, layout, and interaction ids exist in `config/`
- scenario-required sections and components are present
- links, shell links, logos, and media paths use supported schemes and repository-local paths
- raw SVG diagram content parses as SVG XML and passes the strict tag and attribute allowlist
- project profile files under `.cast-docs/` are consistent and path-safe
- rendered HTML passes `config/html-profile.json`
- visual lint and fixture freshness remain green

Do not duplicate every Python semantic rule inside JSON Schema. The schema should define shape; Python should enforce context-aware meaning and safety.

## Drift Guard

In the `CAST-docs/cast-a-doc` repository checkout, run `scripts/validate_schema_contract.py` when changing:

- `schemas/doc.schema.json`
- `scripts/cast_docs_validation.py`
- block payload validation
- diagram or raw SVG behavior
- examples that exercise newly supported document shape

Run `scripts/check_fixtures.py` after contract or renderer changes so checked-in examples, site pages, plan pages, and spec pages remain fresh.

## Compatibility Policy

Existing valid JSON documents should keep rendering unless a release explicitly documents a breaking change. Prefer additive schema changes and validator warnings before rejection when tightening rules.

When a breaking change is unavoidable:

1. Record the change in `site/changelist.json`.
2. Update examples and references in the same commit.
3. Add or update tests for the migration path.
4. Refresh generated HTML artifacts.
5. Mention compatibility impact in the PR or commit description.
