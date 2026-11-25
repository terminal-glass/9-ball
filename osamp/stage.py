"""Stage 49 sub-stage entry points.

The shell and PowerShell files in the repository root are the installer-facing
scripts. They call this module so Linux, macOS, and Windows run the same checks.
This module does not open a network connection and it does not invoke stage 9.
"""

from __future__ import annotations

import sys
import unittest


STAGES = {
    "49-1": {
        "title": "Contract Zero and the foundation",
        "review": "REVIEW-1.md",
        "tests": ["tests.test_foundation", "tests.test_conformance"],
        "pieces": [
            "Contract Zero: human oversight and safe hold",
            "Covenant and the three state boards",
            "Local Postbox",
            "Deterministic gate",
            "Local profile and capacity",
        ],
    },
    "49-2": {
        "title": "Peer, Tribe, Clan, Table, and Work",
        "review": "REVIEW-2.md",
        "tests": ["tests.test_agreements"],
        "pieces": [
            "Peer contract",
            "Tribe contract",
            "Clan contract and bridge acceptance",
            "Table contract",
            "Work contract: Project and Corridor",
        ],
    },
    "49-3": {
        "title": "Receipts, catch-up, restore, and the ledger",
        "review": "REVIEW-3.md",
        "tests": ["tests.test_records_49_3"],
        "pieces": [
            "Separate delivery, acceptance, and completion receipts",
            "Catch-up limited to an accepted role",
            "Tombstones that survive a snapshot restore",
            "Late results and revoked work stay refused",
            "Conformance ledger for all 29 checks",
        ],
    },
    "49-4": {
        "title": "Data, retention, and security schedules",
        "review": "REVIEW-4.md",
        "tests": ["tests.test_schedules_49_4"],
        "pieces": [
            "Data schedule",
            "Retention schedule",
            "Local backup deletion",
            "Security schedule for notices and tools",
            "Traceability rows for these schedules",
        ],
    },
}


def stage_ids() -> list[str]:
    return sorted(STAGES, key=lambda item: int(item.split("-", 1)[1]))


def _print_stage(stage_id: str, verb: str) -> None:
    meta = STAGES[stage_id]
    print(f"{stage_id} {meta['title']} verb={verb} offline=1 network=none jet_stage_9=untouched")
    print(f"{stage_id} review: {meta['review']}")
    for index, piece in enumerate(meta["pieces"], start=1):
        print(f"{stage_id} piece {index}: {piece}")


def run_stage(stage_id: str, verb: str) -> int:
    if stage_id not in STAGES:
        print(f"{stage_id}: unknown sub-stage", file=sys.stderr)
        return 2
    if verb in {"-h", "--help"}:
        print(
            f"Usage: bash {stage_id}.sh [--dry-run|--status|--verify|--install|--configure|--refresh|--repair|--help]\n"
            "  Default is --dry-run. No packages and no network.\n"
            "  Stage 9 is not called.\n"
            f"  Review note: {STAGES[stage_id]['review']}"
        )
        return 0
    known = {
        "--dry-run",
        "--status",
        "--verify",
        "--install",
        "--configure",
        "--refresh",
        "--repair",
    }
    if verb not in known:
        print(f"{stage_id}: unknown argument: {verb}", file=sys.stderr)
        return 2
    _print_stage(stage_id, verb)
    if verb == "--status":
        print(f"{stage_id} status: local records only; no install; stage 9 was not run")
        return 0
    if verb == "--verify":
        suite = unittest.defaultTestLoader.loadTestsFromNames(STAGES[stage_id]["tests"])
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        return 0 if result.wasSuccessful() else 1
    if verb == "--dry-run":
        print(f"{stage_id} dry-run: would run {', '.join(STAGES[stage_id]['tests'])}")
        return 0
    print(f"{stage_id} {verb}: this copy does not install packages or contact another computer")
    print(f"{stage_id} dry-run: would run {', '.join(STAGES[stage_id]['tests'])}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print("Usage: python3 -m osamp.stage <49-N> [--dry-run|--status|--verify|--help]")
        print("Stage 9 is not called.")
        return 0 if args else 2
    if len(args) > 2:
        print(f"{args[0]}: too many arguments", file=sys.stderr)
        return 2
    verb = args[1] if len(args) == 2 else "--dry-run"
    return run_stage(args[0], verb)


if __name__ == "__main__":
    raise SystemExit(main())
