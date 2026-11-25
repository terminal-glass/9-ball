#!/usr/bin/env bash
# macOS counterpart of 49-3. Same five record pieces as 49-3.sh.
# Offline-first. Does not call stage 9.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERB="${1:---dry-run}"
cd "$ROOT"
echo "49-3-mac platform=macos"
exec python3 -m osamp.stage 49-3 "$VERB"
