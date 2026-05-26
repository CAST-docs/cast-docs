# Design Laws

CAST Docs follows these laws when generating documents, designing schema, implementing renderers, or adding new components.

## 1. Consistent Output

Generated HTML must keep a stable document shell, section order pattern, class vocabulary, spacing rhythm, typography scale, and visual treatment across document types.

Do:

- Use the shared base template.
- Use semantic classes from the controlled HTML profile.
- Keep document header, table of contents, body sections, and footer structurally consistent.
- Add new styles only as shared template styles or approved component styles.

Do not:

- Generate one-off layouts for a single document.
- Emit random utility classes.
- Change typography, spacing, colors, or section chrome per request unless the profile explicitly supports it.

Interactive behavior must also be consistent. Approved interactions, such as diagram zoom/download, belong to the shared template. Individual documents must not invent bespoke scripts.

## 2. On-Demand Composition

Load and render only the components, sections, validators, and helper behavior required by the chosen document type, scenario skeleton, and user content.

Do:

- Select the smallest sufficient document type.
- Include optional components only when the content needs them.
- Keep unused sections out unless the scenario skeleton marks them as required.
- Keep generated HTML self-contained without bundling unused functionality.

Do not:

- Add every available component by default.
- Inflate prompts or intermediate JSON with irrelevant blocks.
- Include decorative or speculative sections just because the component exists.

The generator should produce a compact assembly manifest before rendering. The manifest records document type, scenario skeleton, required sections, required components, optional components that were triggered, and omitted components.

## 3. Scenario Skeletons

When the user intent implies a specific scenario, start from the closest document type and apply the scenario skeleton before writing content.

Scenario skeletons define the required high-level sections for a class of work. They may refine a base document type, but should not fork a new document type unless reuse would become unclear.

Scenario skeletons must be declared in configuration, not hard-coded in renderer branches. The renderer consumes selected sections and components from the assembly manifest.

Scenario skeletons define the minimum required structure, not the maximum allowed component set. A scenario may load additional components when they explain the content better, such as sequence diagrams for call chains, diff blocks for code or schema deltas, tables for comparisons, or details blocks for logs. These additions must be selected by trigger rules and recorded in the assembly manifest.

Example: `problem-investigation`

- Background
- Problem symptoms
- Impact scope
- Investigation path
- Core logs and evidence
- Root cause
- Mitigation and fix
- Validation
- Prevention measures
- Open questions

If multiple skeletons could fit, present options and ask the user to choose.

## 4. Reuse First

Prefer reuse before adding new schema shapes, components, styles, validators, or prompt instructions.

Reuse priority:

1. Existing document type.
2. Existing scenario skeleton.
3. Existing component.
4. Existing semantic class.
5. Existing schema fragment.
6. New structure only when reuse would obscure meaning.

This keeps generated output stable and reduces token usage during generation and review.

Implementation implication: keep fixed templates, shared CSS, validators, and examples out of the generation prompt whenever a renderer can load them directly. The model should emit compact structured content and an assembly manifest, not a full copied template.
