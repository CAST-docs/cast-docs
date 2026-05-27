#!/usr/bin/env bash
set -euo pipefail

INPUT="${1:-examples/problem-investigation.json}"
OUTPUT="${2:-out.html}"

cd "$(dirname "$0")/.."

python3 scripts/render_html.py \
  --input "$INPUT" \
  --output "$OUTPUT" \
  --validate

echo "Rendered CAST Docs HTML: $OUTPUT"
