# Document Types

CAST Docs initially supports five static technical document types.

Document type selection must follow `references/design-laws.md`: pick the smallest sufficient base type, then apply a scenario skeleton only when the user intent calls for one.

## engineering-spec

Use for design specifications that describe how a system or feature should work.

Required sections:

- Summary
- Background
- Goals
- Non-goals
- Design
- Data model / API / interfaces, when applicable
- Edge cases
- Security and privacy
- Testing plan
- Rollout plan
- Open questions

## engineering-plan

Use for execution plans that describe how engineering work will be delivered.

Required sections:

- Summary
- Background
- Goals
- Non-goals
- Current state
- Proposed plan
- Alternatives considered
- Risks
- Milestones
- Acceptance criteria
- Open questions

## product-requirement

Use for product requirements, user needs, requirements, flows, and success metrics.

Required sections:

- Summary
- Problem
- Users
- Goals
- Non-goals
- Requirements
- User flows
- Metrics
- Dependencies
- Risks
- Open questions

## decision-record

Use for decisions that need context, tradeoffs, and follow-up actions.

Required sections:

- Context
- Decision
- Options considered
- Tradeoffs
- Consequences
- Follow-ups

## research-note

Use for research notes that separate question, evidence, interpretation, and recommendations.

Required sections:

- Summary
- Question
- Findings
- Evidence
- Interpretation
- Limitations
- Recommendations
- Next steps

## Scenario Skeletons

Scenario skeletons refine a base document type for common work scenes. They are not separate top-level document types unless reuse would become unclear.

Before generating, declare the selected base document type, selected scenario skeleton, required section list, and triggered optional components.

### problem-investigation

Use when documenting incident analysis, defect diagnosis, production issue investigation, or complex problem localization.

Recommended base type: `engineering-plan` for action-oriented follow-up, or `research-note` when the output is mostly diagnostic evidence.

Required sections:

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

If the request could be either `problem-investigation` or another skeleton, ask the user to choose before generating.

### cross-team-alignment

Use when documenting cross-team differences, source-of-truth gaps, ownership boundaries, or coordination actions.

Recommended base type: `engineering-plan` when follow-up work is expected, or `decision-record` when the output records an agreed direction.

Required sections:

- Background
- Participants and responsibilities
- Source of truth
- Differences or gaps
- Impact
- Decisions
- Action items
- Open questions

### option-decision

Use when comparing options, choosing an implementation path, or recording an architecture decision.

Recommended base type: `decision-record`.

Required sections:

- Context
- Decision criteria
- Options considered
- Comparison
- Decision
- Tradeoffs
- Follow-ups

### document-digest

Use when summarizing one or more source documents for fast review.

Recommended base type: `research-note`.

Required sections:

- Summary
- Source documents
- Key findings
- Cross-document relationships, when applicable
- Limitations
- Next steps

Do not add a repeated FAQ or recap section when the same points already appear in the findings.

### principle-showcase

Use when explaining principles, standards, design rules, or feature sets.

Recommended base type: `engineering-spec` when the principles drive implementation, or `research-note` when they are explanatory.

Required sections:

- Summary
- Context
- Principles or features
- Examples
- Application guidance
- Open questions
