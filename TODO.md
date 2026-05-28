# cast-a-doc TODO

This list was created by a `cast-a-start` guided rewrite pass on 2026-05-28.

## Rewrite Follow-Ups

- Decide how much of an existing repository `cast-a-start` may rewrite by default: links only, planning workspace, implementation docs, or full documentation replacement.
- Add an explicit rewrite questionnaire for target repositories that already contain README, skill files, examples, or generated documentation.
- Define how `cast-a-start` should summarize preserved files, rewritten files, and deferred files after a migration.

## Product Follow-Ups

- Add a schema versioning policy for generated CAST Docs JSON documents.
- Decide whether the renderer should expose a small CLI wrapper in addition to direct Python script usage.
- Add a visual regression workflow for representative generated pages.
- Expand project profile examples for real repositories with multiple document sets.

## Documentation Follow-Ups

- Keep `plan/` and `spec/` in sync with renderer changes that affect authoring behavior.
- Add a short "when to use cast-a-doc vs cast-a-start" comparison once both skills stabilize.
- Capture compatibility notes for Codex, Claude Code, local browser viewing, and GitHub Pages publishing.
