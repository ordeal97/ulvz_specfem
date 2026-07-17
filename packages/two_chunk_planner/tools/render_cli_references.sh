#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for command in pandoc wkhtmltopdf pdfinfo pdftotext; do
  command -v "$command" >/dev/null || { echo "missing required command: $command" >&2; exit 2; }
done
WORK="$(mktemp -d "${TMPDIR:-/tmp}/two_chunk_planner_pdf.XXXXXX")"
for language in en zh; do
  markdown="$ROOT/docs/cli_reference_${language}.md"
  html="$WORK/${language}.html"
  pdf="$ROOT/docs/cli_reference_${language}.pdf"
  pandoc --from=gfm --standalone --self-contained --resource-path="$ROOT/docs:$ROOT" \
    --css="$ROOT/docs/cli_reference.css" --metadata title="two_chunk_planner CLI reference (${language})" \
    "$markdown" -o "$html"
  sed -i "s|<head>|<head><base href=\"file://$ROOT/docs/\">|" "$html"
  wkhtmltopdf --enable-local-file-access --encoding utf-8 --page-size A4 \
    --margin-top 14mm --margin-bottom 14mm --margin-left 12mm --margin-right 12mm "$html" "$pdf" >/dev/null
  pdfinfo "$pdf" | sed -n '1,12p'
done
