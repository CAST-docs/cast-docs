# cast-a-doc CHANGELIST

## 2026-05-28

- Added `.cast-docs/project.json` style profiles for standardized project-level theme, density, surface, accent, and token override control.
- Kept style customization renderer-owned: profile values compile into CSS variables, while document JSON remains semantic and does not carry CSS classes.
- Ran a `cast-a-start` guided rewrite pass over `cast-a-doc`.
- Preserved the existing renderer implementation, skill manifest, examples, references, install flow, and generated site pages.
- Added `plan/` as a product planning workspace.
- Added `spec/` as a technical design workspace.
- Added repository-level `TODO.md` and `CHANGELIST.md`.
- Linked the new planning workspace from `README.md` and the landing page.

## Rewrite Policy Used

The rewrite used the guided migration mode: keep working implementation artifacts intact, add explicit planning and specification documents beside them, and only modify existing entry points to expose the new documentation.
