#!/usr/bin/env bash
# macOS counterpart of 49-1. Same five foundation pieces as 49-1.sh.
# Offline-first. Does not call stage 9.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERB="${1:---dry-run}"
cd "$ROOT"
echo "49-1-mac platform=macos"
exec python3 -m osamp.stage 49-1 "$VERB"
