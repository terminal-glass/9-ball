#!/usr/bin/env bash
# 49-1 - Contract Zero and the foundation.
# Pieces: Contract Zero, covenant and three state boards, Postbox, gate, profile.
# Offline-first. Does not call stage 9.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERB="${1:---dry-run}"
cd "$ROOT"
exec python3 -m osamp.stage 49-1 "$VERB"
