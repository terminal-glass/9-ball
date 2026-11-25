#!/usr/bin/env bash
# 49-3 - Receipts, catch-up, restore, and the conformance ledger.
# Offline-first. Does not call stage 9.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERB="${1:---dry-run}"
cd "$ROOT"
exec python3 -m osamp.stage 49-3 "$VERB"
