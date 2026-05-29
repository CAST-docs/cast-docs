#!/usr/bin/env bash
set -euo pipefail

REPOSITORY="${CAST_A_DOC_REPOSITORY:-CAST-docs/cast-a-doc}"
SKILL_NAME="${CAST_A_DOC_SKILL:-cast-a-doc}"
AGENT="${CAST_A_DOC_AGENT:-codex}"
SCOPE="${CAST_A_DOC_SCOPE:-user}"
PIN="${CAST_A_DOC_VERSION:-}"
FORCE="${CAST_A_DOC_FORCE:-1}"

usage() {
  cat <<'EOF'
cast-a-doc skill installer

Usage:
  install.sh [--codex|--claude|--both]
  install.sh [--agent codex|claude-code|both] [--scope user|project]

Examples:
  curl -fsSL https://cast-docs.github.io/cast-a-doc/install.sh | bash
  curl -fsSL https://cast-docs.github.io/cast-a-doc/install.sh | bash -s -- --claude
  curl -fsSL https://cast-docs.github.io/cast-a-doc/install.sh | bash -s -- --both
  gh skill install CAST-docs/cast-a-doc cast-a-doc --agent codex --scope user

Environment:
  CAST_A_DOC_REPOSITORY  GitHub repository in OWNER/REPO format.
  CAST_A_DOC_SKILL       Skill name or repository path. Defaults to cast-a-doc.
  CAST_A_DOC_VERSION     Optional tag or commit SHA to pin.
  CAST_A_DOC_AGENT       codex, claude-code, or both. Defaults to codex.
  CAST_A_DOC_SCOPE       user or project. Defaults to user.
  CAST_A_DOC_FORCE       Set to 0 to skip gh skill install --force.

Requires GitHub CLI with `gh skill install` support.
EOF
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

require_gh_skill() {
  if ! command -v gh >/dev/null 2>&1; then
    die "GitHub CLI is required. Install or upgrade gh, then run this installer again."
  fi

  if ! gh skill install --help >/dev/null 2>&1; then
    die "this gh version does not support 'gh skill install'. Upgrade GitHub CLI to a version with skill support."
  fi
}

normalize_agent() {
  case "$1" in
    codex) printf 'codex\n' ;;
    claude|claude-code) printf 'claude-code\n' ;;
    both) printf 'both\n' ;;
    *) die "unknown agent '$1'; expected codex, claude-code, or both" ;;
  esac
}

normalize_scope() {
  case "$1" in
    user|project) printf '%s\n' "$1" ;;
    *) die "unknown scope '$1'; expected user or project" ;;
  esac
}

install_skill() {
  agent="$1"

  args=(skill install "$REPOSITORY" "$SKILL_NAME" --agent "$agent" --scope "$SCOPE")
  if [ -n "$PIN" ]; then
    args+=(--pin "$PIN")
  fi
  if [ "$FORCE" != "0" ]; then
    args+=(--force)
  fi

  printf 'Installing or updating cast-a-doc for %s with gh skill install.\n' "$agent"
  gh "${args[@]}"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --codex)
      AGENT="codex"
      ;;
    --claude)
      AGENT="claude-code"
      ;;
    --both)
      AGENT="both"
      ;;
    --agent)
      [ "$#" -ge 2 ] || die "--agent requires codex, claude-code, or both"
      AGENT="$2"
      shift
      ;;
    --agent=*)
      AGENT="${1#--agent=}"
      ;;
    --scope)
      [ "$#" -ge 2 ] || die "--scope requires user or project"
      SCOPE="$2"
      shift
      ;;
    --scope=*)
      SCOPE="${1#--scope=}"
      ;;
    --repository)
      [ "$#" -ge 2 ] || die "--repository requires OWNER/REPO"
      REPOSITORY="$2"
      shift
      ;;
    --repository=*)
      REPOSITORY="${1#--repository=}"
      ;;
    --pin|--version)
      [ "$#" -ge 2 ] || die "$1 requires a tag or commit SHA"
      PIN="$2"
      shift
      ;;
    --pin=*|--version=*)
      PIN="${1#*=}"
      ;;
    --no-force)
      FORCE="0"
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

if [ -n "${CAST_A_DOC_REPO_URL:-}" ] || [ -n "${CAST_DOCS_REPO_URL:-}" ]; then
  die "CAST_A_DOC_REPO_URL and CAST_DOCS_REPO_URL are no longer supported. Use CAST_A_DOC_REPOSITORY in OWNER/REPO format."
fi
if [ -n "${CAST_A_DOC_SKILL_DIR:-}" ] || [ -n "${CAST_DOCS_SKILL_DIR:-}" ]; then
  die "custom skill directories are no longer supported by this installer. Use gh skill install --scope user|project."
fi

AGENT="$(normalize_agent "$AGENT")"
SCOPE="$(normalize_scope "$SCOPE")"

require_gh_skill

if [ "$AGENT" = "both" ]; then
  install_skill codex
  install_skill claude-code
else
  install_skill "$AGENT"
fi

printf 'Done. Restart the agent app if it was already running.\n'
