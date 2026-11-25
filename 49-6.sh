#!/usr/bin/env bash
# 49-6 - Shared vectors, a second small gate, and the requirement trace.
# Offline-first. Does not call stage 9. Does not claim interoperability.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERB="${1:---dry-run}"
cd "$ROOT"
exec python3 -m osamp.stage 49-6 "$VERB"
