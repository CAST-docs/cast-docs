# Writing Style

`cast-a-doc` output should be concise, stable, and easy to review in Git.

## Rules

- Prefer concrete nouns and verbs.
- Avoid marketing language.
- Avoid vague adjectives.
- Keep sections short.
- Separate facts from assumptions.
- Mark unknowns explicitly.
- Use bullets for criteria and action lists.
- Use tables for comparisons and structured tradeoffs.
- Preserve technical precision.
- Do not over-explain obvious context.
- Do not invent critical facts.

## Inline Marks

Prose fields accept inline runs with typed marks (see Generation Contract → Inline Text Formatting). Use them sparingly and for meaning, not decoration:

- Prefer `code` for identifiers, paths, symbols, and config keys.
- Use semantic marks (`deprecated`, `term`, `metric`, `ref`) to carry meaning a coding agent can read.
- Use `del` for superseded values and `metric` for measured numbers (keep the unit/value in the mark).
- At most one visual plus one semantic mark per run; do not stack visual marks.
- Do not nest a semantic mark inside `code`.

## Tone

Use direct technical prose. The document should read like a durable engineering artifact, not a landing page or pitch.
