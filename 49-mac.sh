#!/usr/bin/env bash
# macOS counterpart of the stage 49 controller.
# Calls 49-1-mac.sh, 49-2-mac.sh, and later macOS sub-stages in order.
# Offline-first. Does not call stage 9.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERB="${1:---dry-run}"

usage() {
  cat <<'EOF'
Usage: bash 49-mac.sh [--dry-run|--status|--verify|--install|--configure|--refresh|--repair|--help]
  macOS entry for the same contract groups as 49.sh.
  Default is --dry-run. No packages and no network. Stage 9 is not called.
EOF
}

case "$VERB" in
  -h|--help) usage; exit 0 ;;
  --dry-run|--status|--verify|--install|--configure|--refresh|--repair) ;;
  *) echo "49-mac: unknown argument: ${VERB}" >&2; usage >&2; exit 2 ;;
esac

echo "49-mac 9-Ball controller verb=${VERB} offline=1 network=none jet_stage_9=untouched platform=macos"
found=0
n=1
while [[ "$n" -le 30 ]]; do
  stage="${ROOT}/49-${n}-mac.sh"
  if [[ -f "$stage" ]]; then
    found=1
    bash "$stage" "$VERB"
  fi
  n=$((n + 1))
done
if [[ "$found" -eq 0 ]]; then
  echo "49-mac: no sub-stages were present" >&2
  exit 1
fi
exit 0
