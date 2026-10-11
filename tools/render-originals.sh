#!/usr/bin/env bash
# Render the synthetic image originals (invoice, chat screenshot) from their HTML sources.
# Needs Node.js; Playwright downloads its browser on first run (`npx playwright install chromium`).
set -euo pipefail

cd "$(dirname "$0")/../agent/app/payguard/data/originals"
PLAYWRIGHT="npx -y playwright@1.60.0"
HERE="$(pwd -W 2>/dev/null || pwd)"  # Windows Git Bash needs a drive-letter path in file:// URLs

$PLAYWRIGHT screenshot --viewport-size=760,900 --full-page "file:///${HERE#/}/src/routine-invoice.invoice.html" routine-invoice.invoice.png
$PLAYWRIGHT screenshot --viewport-size=390,760 --full-page "file:///${HERE#/}/src/ceo-chat.line.html" ceo-chat.line.png
