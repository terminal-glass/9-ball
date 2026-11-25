#!/usr/bin/env bash
# 49-4 - Data, retention, and security schedules.
# Offline-first. Does not call stage 9.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERB="${1:---dry-run}"
cd "$ROOT"
exec python3 -m osamp.stage 49-4 "$VERB"
