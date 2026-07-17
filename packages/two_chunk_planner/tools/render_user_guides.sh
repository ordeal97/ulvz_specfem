#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for command in pandoc wkhtmltopdf pdfinfo pdftotext; do command -v "$command" >/dev/null || exit 2; done
WORK="$(mktemp -d "${TMPDIR:-/tmp}/two_chunk_user_guides.XXXXXX")"
for language in en zh; do
  pandoc --from=gfm --standalone --self-contained --resource-path="$ROOT/docs:$ROOT" --css="$ROOT/docs/cli_reference.css" "$ROOT/docs/user_guide_${language}.md" -o "$WORK/$language.html"
  sed -i "s|<head>|<head><base href=\"file://$ROOT/docs/\">|" "$WORK/$language.html"
  wkhtmltopdf --enable-local-file-access --encoding utf-8 --page-size A4 --margin-top 14mm --margin-bottom 14mm --margin-left 12mm --margin-right 12mm "$WORK/$language.html" "$ROOT/docs/user_guide_${language}.pdf" >/dev/null
  pdfinfo "$ROOT/docs/user_guide_${language}.pdf" | sed -n '1,12p'
done
