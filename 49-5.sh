#!/usr/bin/env bash
# 49-5 - Acknowledgment, Project and Corridor schedules, measurement, and crash recovery.
# Offline-first. Does not call stage 9.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERB="${1:---dry-run}"
cd "$ROOT"
exec python3 -m osamp.stage 49-5 "$VERB"
