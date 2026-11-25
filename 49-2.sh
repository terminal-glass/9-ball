#!/usr/bin/env bash
# 49-2 - Peer, Tribe, Clan, Table, and Work.
# Offline-first. A bridge note stays on this computer. Does not call stage 9.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERB="${1:---dry-run}"
cd "$ROOT"
exec python3 -m osamp.stage 49-2 "$VERB"
