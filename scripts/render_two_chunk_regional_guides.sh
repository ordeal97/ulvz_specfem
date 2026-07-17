#!/usr/bin/env bash
# Render the bilingual canonical two-chunk guides to PDF without touching SPECFEM.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for command in pandoc wkhtmltopdf pdfinfo pdftotext; do
  command -v "$command" >/dev/null || { echo "missing required command: $command" >&2; exit 2; }
done

WORK="$(mktemp -d "${TMPDIR:-/tmp}/two_chunk_guide_pdf.XXXXXX")"
CSS="$ROOT/docs/assets/two_chunk_guide_pdf.css"
render() {
  local language="$1"
  local markdown="$ROOT/docs/two_chunk_regional_simulations_guide_${language}.md"
  local html="$WORK/${language}.html"
  local pdf="$ROOT/docs/two_chunk_regional_simulations_guide_${language}.pdf"
  pandoc --from=gfm --standalone --self-contained --resource-path="$ROOT/docs:$ROOT" --css="$CSS" \
    --metadata title="Canonical two-chunk regional simulations (${language})" \
    "$markdown" -o "$html"
  # Keep Markdown cross-references relative to docs/ after the intermediate
  # HTML is placed in /tmp for rendering.
  sed -i "s|<head>|<head><base href=\"file://$ROOT/docs/\">|" "$html"
  wkhtmltopdf --enable-local-file-access --encoding utf-8 --page-size A4 \
    --margin-top 16mm --margin-bottom 16mm --margin-left 14mm --margin-right 14mm \
    "$html" "$pdf" >/dev/null
  pdfinfo "$pdf" | sed -n '1,12p'
  echo "rendered $pdf (intermediate files retained in $WORK)"
}
render en
render zh
