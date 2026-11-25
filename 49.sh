#!/usr/bin/env bash
# 49 - 9-Ball controller.
# Calls 49-1.sh, 49-2.sh, and later sub-stages in numeric order.
# Offline-first. Does not call, rename, or replace 9.sh. Stage 9 stays untouched.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERB="${1:---dry-run}"

usage() {
  cat <<'EOF'
Usage: bash 49.sh [--dry-run|--status|--verify|--install|--configure|--refresh|--repair|--help]
  Default is --dry-run. No packages and no network.
  The controller runs each present 49-N.sh in order and passes the same verb.
  Stage 9 is not called.
EOF
}

case "$VERB" in
  -h|--help) usage; exit 0 ;;
  --dry-run|--status|--verify|--install|--configure|--refresh|--repair) ;;
  *) echo "49: unknown argument: ${VERB}" >&2; usage >&2; exit 2 ;;
esac

echo "49 9-Ball controller verb=${VERB} offline=1 network=none jet_stage_9=untouched"
found=0
n=1
while [[ "$n" -le 30 ]]; do
  stage="${ROOT}/49-${n}.sh"
  if [[ -f "$stage" ]]; then
    found=1
    bash "$stage" "$VERB"
  fi
  n=$((n + 1))
done
if [[ "$found" -eq 0 ]]; then
  echo "49: no sub-stages were present" >&2
  exit 1
fi
exit 0
