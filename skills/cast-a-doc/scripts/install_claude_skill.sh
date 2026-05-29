#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${CAST_A_DOC_REPO_URL:-${CAST_DOCS_REPO_URL:-https://github.com/CAST-docs/cast-a-doc.git}}"
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
TARGET="${CAST_A_DOC_SKILL_DIR:-${CAST_DOCS_SKILL_DIR:-$CLAUDE_HOME/skills/cast-a-doc}}"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required to install the cast-a-doc Claude Code skill." >&2
  exit 1
fi

mkdir -p "$(dirname "$TARGET")"

if [ -d "$TARGET/.git" ]; then
  git -C "$TARGET" pull --ff-only
elif [ -e "$TARGET" ]; then
  echo "Target exists but is not a git checkout: $TARGET" >&2
  exit 1
else
  git clone "$REPO_URL" "$TARGET"
fi

if [ ! -f "$TARGET/SKILL.md" ]; then
  echo "Installed checkout is missing SKILL.md: $TARGET" >&2
  exit 1
fi

echo "cast-a-doc Claude Code skill installed at: $TARGET"
