#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${CAST_A_DOC_REPO_URL:-${CAST_DOCS_REPO_URL:-https://github.com/CAST-docs/cast-a-doc.git}}"
AGENT="${CAST_A_DOC_AGENT:-${CAST_DOCS_AGENT:-codex}}"
SKILL_DIR="${CAST_A_DOC_SKILL_DIR:-${CAST_DOCS_SKILL_DIR:-}}"

usage() {
  cat <<'EOF'
cast-a-doc skill installer

Usage:
  install.sh [--codex|--claude|--both]

Examples:
  curl -fsSL https://cast-docs.github.io/cast-a-doc/install.sh | bash
  curl -fsSL https://cast-docs.github.io/cast-a-doc/install.sh | bash -s -- --claude
  curl -fsSL https://cast-docs.github.io/cast-a-doc/install.sh | bash -s -- --both

Environment:
  CAST_A_DOC_REPO_URL   Git repository to clone or update.
  CAST_A_DOC_AGENT      codex, claude, or both. Defaults to codex.
  CAST_A_DOC_SKILL_DIR  Override target directory for a single-agent install.
  CAST_DOCS_*           Deprecated aliases for the CAST_A_DOC_* variables.
  CODEX_HOME            Codex home directory. Defaults to ~/.codex.
  CLAUDE_HOME           Claude Code home directory. Defaults to ~/.claude.
EOF
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

require_git() {
  if ! command -v git >/dev/null 2>&1; then
    die "git is required to install cast-a-doc."
  fi
}

normalize_agent() {
  case "$1" in
    codex|claude|both) printf '%s\n' "$1" ;;
    *) die "unknown agent '$1'; expected codex, claude, or both" ;;
  esac
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --codex)
      AGENT="codex"
      ;;
    --claude)
      AGENT="claude"
      ;;
    --both)
      AGENT="both"
      ;;
    --agent)
      [ "$#" -ge 2 ] || die "--agent requires codex, claude, or both"
      AGENT="$2"
      shift
      ;;
    --agent=*)
      AGENT="${1#--agent=}"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
  shift
done

AGENT="$(normalize_agent "$AGENT")"

target_for_agent() {
  case "$1" in
    codex)
      if [ -n "$SKILL_DIR" ]; then
        printf '%s\n' "$SKILL_DIR"
      else
        printf '%s\n' "${CODEX_HOME:-$HOME/.codex}/skills/cast-a-doc"
      fi
      ;;
    claude)
      if [ -n "$SKILL_DIR" ]; then
        printf '%s\n' "$SKILL_DIR"
      else
        printf '%s\n' "${CLAUDE_HOME:-$HOME/.claude}/skills/cast-a-doc"
      fi
      ;;
    *)
      die "unsupported agent: $1"
      ;;
  esac
}

install_agent() {
  agent="$1"
  target="$(target_for_agent "$agent")"

  mkdir -p "$(dirname "$target")"

  if [ -d "$target/.git" ]; then
    printf 'Updating cast-a-doc %s skill at: %s\n' "$agent" "$target"
    git -C "$target" pull --ff-only
  elif [ -e "$target" ]; then
    die "target exists but is not a git checkout: $target"
  else
    printf 'Installing cast-a-doc %s skill at: %s\n' "$agent" "$target"
    git clone "$REPO_URL" "$target"
  fi

  if [ ! -f "$target/SKILL.md" ]; then
    die "installed checkout is missing SKILL.md: $target"
  fi

  printf 'cast-a-doc %s skill ready at: %s\n' "$agent" "$target"
}

require_git

if [ "$AGENT" = "both" ]; then
  if [ -n "$SKILL_DIR" ]; then
    die "CAST_A_DOC_SKILL_DIR can only be used with a single-agent install"
  fi
  install_agent codex
  install_agent claude
else
  install_agent "$AGENT"
fi

printf 'Done. Restart the agent app if it was already running.\n'
