# Review 3 — stage 49-3, receipts, catch-up, restore, and the ledger

This is installer stage **49-3**. `49.sh` calls `49-1.sh`, then `49-2.sh`, then `49-3.sh`. Read the earlier review notes for the foundation and the five agreements.

| Platform | Controller | This group |
| --- | --- | --- |
| Linux | `49.sh` | `49-3.sh` |
| macOS | `49-mac.sh` | `49-3-mac.sh` |
| Windows | `49-windows.ps1` | `49-3-windows.ps1` |

```text
bash 49-3.sh --dry-run
bash 49-3.sh --status
bash 49-3.sh --verify
bash 49.sh --dry-run
python3 -m osamp.conformance
```

## The five pieces

1. **Separate receipts.** An arrived message gets a delivery receipt. That receipt does not accept a role.
2. **Catch-up.** Only an accepted role can receive one. It carries a short summary, evidence fingerprints, uncertainty, the subtask, and the contract version. A transcript is refused. A private-medical placeholder is refused on a public-news route.
3. **Tombstones.** Revocation, spent budget, and closure are appended beside the database. Restoring an older snapshot reapplies them. Spend does not go backwards and a revocation comes back.
4. **Late results.** A result after revocation is refused. STOP_PENDING and an uncertain outside effect still survive a reopen, and the outside effect is not repeated.
5. **Conformance ledger.** `python3 -m osamp.conformance` prints all 29 checks. This stage's tests fail if any check's status is fail.

## Requirement to code and test

| Piece | Requirements | Checks |
| --- | --- | --- |
| Receipts | B-MSG03 | `test_delivery_receipt_does_not_accept_the_role` |
| Catch-up | B-DATA02, WP-11 | WP-11 pass |
| Tombstones | P-QUEUE03, CZ-28 | `test_restore_keeps_revocation_and_spent_budget`; CZ-28 partial |
| Late results | P-MSG04, B-CTRL02 | inside CZ-28 and the restore test |
| Ledger | section 11 | `test_ledger_has_no_failures` |

## Test evidence

Python 3.12.3:

```text
python3 -m unittest discover -s tests -v
python3 -m osamp.conformance
bash 49-3.sh --verify
```

Result: **21 unit tests, all OK.** Conformance: **24 pass, 4 partial, 1 pending, 0 fail.** WP-11 now passes. Still partial: WP-04, WP-10, CZ-28, CZ-29. Still pending: WP-12 only.

## Known limitations

- The medical example is the text "placeholder only, not a real record". It is not health data.
- Restore is a file copy plus the sidecar. Physical power was not cut. CZ-28 stays partial for that reason.
- There is still no second backup store, so WP-10 stays partial.
- There is still one Python implementation, so WP-12 stays pending.
- Mac and Windows entry points call this same code. They are not an independent adapter.
- Stage 9 is not called. The installer repository was not modified.

## Questions for reviewers

1. Is a sidecar file next to the database the right place for tombstones, or should they live somewhere the snapshot cannot omit?
2. Should a delivery receipt expire with the invitation body, or stay as a one-line arrival record?
3. Is "designated-review" an acceptable catch-up route name until the real recipient list is chosen?
