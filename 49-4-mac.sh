#!/usr/bin/env bash
# macOS counterpart of 49-4. Same five schedule pieces as 49-4.sh.
# Offline-first. Does not call stage 9.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERB="${1:---dry-run}"
cd "$ROOT"
echo "49-4-mac platform=macos"
exec python3 -m osamp.stage 49-4 "$VERB"
