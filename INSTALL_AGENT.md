# CAST Docs Agent Install

Use this when you want a coding agent to install CAST Docs as a local renderer or as an agent skill.

## Codex Skill

```bash
git clone https://github.com/CAST-docs/cast-docs.git /tmp/cast-docs
/tmp/cast-docs/scripts/install_codex_skill.sh
```

This installs or updates the skill at `~/.codex/skills/cast-docs`.

## Claude Code Skill

```bash
git clone https://github.com/CAST-docs/cast-docs.git /tmp/cast-docs
/tmp/cast-docs/scripts/install_claude_skill.sh
```

This installs or updates the skill at `~/.claude/skills/cast-docs`.

## Local Renderer Smoke Test

```bash
git clone https://github.com/CAST-docs/cast-docs.git /tmp/cast-docs
cd /tmp/cast-docs
scripts/render_example.sh examples/problem-investigation.json out.html
```

CAST Docs needs Python 3.9 or newer and uses only the Python standard library.
