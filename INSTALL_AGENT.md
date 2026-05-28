# CAST Docs Agent Install

Use this when you want a coding agent to install CAST Docs as a local renderer or as an agent skill.

For the rendered guide with options and troubleshooting, open:

https://cast-docs.github.io/cast-docs/install.html

## Codex Skill

```bash
curl -fsSL https://cast-docs.github.io/cast-docs/install.sh | bash
```

This installs or updates the skill at `~/.codex/skills/cast-docs`.

## Claude Code Skill

```bash
curl -fsSL https://cast-docs.github.io/cast-docs/install.sh | bash -s -- --claude
```

This installs or updates the skill at `~/.claude/skills/cast-docs`.

## Both Agent Skills

```bash
curl -fsSL https://cast-docs.github.io/cast-docs/install.sh | bash -s -- --both
```

## Local Renderer Smoke Test

```bash
git clone https://github.com/CAST-docs/cast-docs.git /tmp/cast-docs
cd /tmp/cast-docs
scripts/render_example.sh examples/problem-investigation.json out.html
```

CAST Docs needs Python 3.9 or newer and uses only the Python standard library.

## Repository Project Profiles

For repeated use inside a target repository, CAST Docs can read a repository-level `.cast-docs/` profile. Use it for team templates, i18n defaults, terminology, writing rules, logos, reusable assets, and output defaults.

Do not create or change `.cast-docs/` unless the user asks the agent to remember repository-specific settings. When no output path is provided, ask whether the generated HTML should go under `docs/cast-docs/` for sharing or `.cast-docs/out/` for local draft output.
