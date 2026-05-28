# CAST Docs Project Profile

This directory is the repository-level CAST Docs profile for this repository.

It is reviewable project configuration, not hidden agent memory. Use it to keep durable CAST Docs defaults close to the repository:

- project metadata and output paths in `project.json`
- generation preferences in `preferences.json`
- locale policy in `i18n.json`
- product terminology in `glossary.json`
- repository writing rules in `writing-style.md`
- reusable templates, examples, and assets in the matching subdirectories

Private drafts and temporary output belong in `out/`, `local/`, or `cache/`; those paths are intentionally ignored by git.
