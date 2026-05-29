# cast-a-doc Agent Install

Use this when you want a coding agent to install the `cast-a-doc` skill or its local renderer.

For the rendered guide with options and troubleshooting, open:

https://cast-docs.github.io/cast-a-doc/install.html

## Codex Skill

```bash
gh skill install CAST-docs/cast-a-doc cast-a-doc --pin v0.1.0 --agent codex --scope user
```

## Claude Code Skill

```bash
gh skill install CAST-docs/cast-a-doc cast-a-doc --pin v0.1.0 --agent claude-code --scope user
```

## Both Agent Skills

```bash
curl -fsSL https://cast-docs.github.io/cast-a-doc/install.sh | bash -s -- --both
```

The compatibility installer delegates to `gh skill install` and does not clone into the current directory.

## Local Renderer Smoke Test

```bash
rm -rf /tmp/cast-a-doc-skill
gh skill install CAST-docs/cast-a-doc cast-a-doc --pin v0.1.0 --dir /tmp/cast-a-doc-skill --force
cd /tmp/cast-a-doc-skill/cast-a-doc
scripts/render_example.sh examples/problem-investigation.json out.html
```

`cast-a-doc` needs Python 3.9 or newer and uses only the Python standard library.

## Repository Project Profiles

For repeated use inside a target repository, `cast-a-doc` can read a repository-level `.cast-docs/` profile. Use it for team templates, i18n defaults, terminology, writing rules, logos, reusable assets, and output defaults.

Do not create or change `.cast-docs/` unless the user asks the agent to remember repository-specific settings. When no output path is provided, ask whether the generated HTML should go under `docs/cast-docs/` for sharing or `.cast-docs/out/` for local draft output.
