# Repository Writing Style

- Treat JSON as the source and rendered HTML as the shareable artifact.
- Prefer concise, operational writing over marketing copy.
- Use English for repository metadata by default; include `zh-CN` variants in rendered public pages when the page already supports bilingual output.
- Keep install documentation focused on the one-line `curl` path first, then link to deeper options.
- Use local links for files published in the same GitHub Pages tree, and GitHub links for source files that readers may want to inspect.
- Mark unknowns explicitly instead of filling gaps with guesses.
- Keep section titles short and stable; machine-readable ids, paths, URLs, component ids, and scenario ids should stay single-valued.
- Do not create or change `.cast-docs/` in another repository unless the user explicitly asks the agent to remember repository-specific settings.
