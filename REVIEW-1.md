# Review 1 — stage 49-1, Contract Zero and the foundation

This is installer stage **49-1**. The controller is `49.sh`. It calls `49-1.sh` and any later `49-N.sh` in order. Stage 9 is not called.

| Platform | Controller | This group |
| --- | --- | --- |
| Linux | `49.sh` | `49-1.sh` |
| macOS | `49-mac.sh` | `49-1-mac.sh` |
| Windows | `49-windows.ps1` | `49-1-windows.ps1` |

`OpenClaw-Installer-Linux`, `OpenClaw-Installer-Mac`, and `OpenClaw-Installer-Windows` only point at those controllers. They do not install OpenClaw. `OSAMP-Linux`, `OSAMP-Mac`, and `OSAMP-Windows` point at the same controllers. Mac and Windows run the same Python checks as Linux. That is one implementation with three entry points, not a second adapter.

```text
bash 49-1.sh --dry-run
bash 49-1.sh --status
bash 49-1.sh --verify
bash 49.sh --dry-run
```

Please review this submission on its own. It is the first of a stack. It does not need the later submissions to be understandable.

Nothing here was merged. A later human go-ahead is required before any merge.

## The five pieces

1. **Contract Zero: human oversight and safe hold.** Acknowledgment, bounded detection of circular or stuck work, a recovery record saved with acceptance, a hold that runs with no language model, STOP_PENDING until a confirmation, a tagged human decision before resume, and no automatic renewal of budget or trust.
2. **Covenant and the three state boards.** Delivery, authority, and execution stay separate. PLAY, PAUSE, STOP, REWIND, REVIEW, FAST-FORWARD, and TIMEOUT are local rules.
3. **Local Postbox.** One SQLite file for offers, accepted duties, receipts, notices, holds, and an audit of identifiers. Unanswered invitations can expire. Accepted duties stay.
4. **Deterministic gate.** Sender allowlist, known message types, size, checksum, and duplicate checks happen before any tool. A signature field is refused because no signature method is adopted.
5. **Local profile and capacity.** Placeholder limits, a governance fingerprint, a size-1 worker, reserved space for the recovery record, and a conformance claim that turns off if the covenant is turned off.

Code lives in `osamp/`. Checks live in `tests/` and `osamp/conformance.py`. The plain guide is `OSAMP-Architecture.md`.

## Requirement to code and test

| Piece | Main requirements | Code | Checks |
| --- | --- | --- | --- |
| 1. Contract Zero | P-Z01–P-Z13, CZ-22–CZ-29 | `osamp/contract_zero.py`, `osamp/auth.py`, `osamp/node.py` | CZ-22 pass; CZ-23 pass; CZ-24 pass; CZ-25 pass; CZ-26 pass; CZ-27 pass; CZ-28 partial; CZ-29 partial |
| 2. Covenant and states | B-CTRL01, B-CTRL02, WP-08, WP-09, WP-16–WP-21 | `osamp/covenant.py`, `osamp/records.py`, `osamp/plain.py` | WP-08 pass; WP-09 pass; WP-16 partial; WP-17 pass; WP-18 pass; WP-19 pass; WP-20 pass; WP-21 pass |
| 3. Postbox | B-QUEUE01, B-RET01, B-QUEUE04, WP-03, WP-07, WP-10 | `osamp/postbox.py` | WP-03 pass; WP-07 pass; WP-10 partial |
| 4. Gate | B-GATE02, WP-01, WP-02 | `osamp/gate.py` | WP-01 pass; WP-02 pass |
| 5. Profile | B-CAP01, P-Z08, WP-04, WP-21 | `osamp/profile.py` | WP-04 partial; CZ-25 pass; WP-21 pass |

Pending in this submission, on purpose: WP-05, WP-06, WP-11, WP-12, WP-13, WP-14, WP-15. They need the five agreements, catch-up, or a second implementation.

## Test evidence

Commands run on Python 3.12.3:

```text
python3 -m unittest discover -s tests -v
python3 -m osamp.conformance
```

Result: 7 unit tests, all OK. Conformance: **17 pass, 5 partial, 7 pending, 0 fail.**

The concurrent-accept test, two threads accepting one offer, was repeated 10 times and passed each time. One obligation was stored and the delegation count dropped by one.

Partial, and why:

- **WP-04.** A local rule names a bounded step and refuses a whole project. There is no measured 1–9 benchmark.
- **WP-10.** Expired invitation text is removed from this SQLite file. There is no backup or second log to delete.
- **WP-16.** Holds and a human "leave held" decision survive reopening the file. Corridor human-satisfaction is not built.
- **CZ-28.** Reopening the file keeps an uncertain outside effect and refuses a blind repeat. Power was not cut. Backup restore is not built.
- **CZ-29.** An agreed closure removes the objective from this file and keeps a disposition. Off-site copies are not deleted because none are made.

Passes that are easy to over-read:

- WP-01 is an allowlist, not a cryptographic signature.
- WP-08 and WP-09 are records on one computer. The "other computer" confirmation is a test input.
- CZ-25 disables a model port. No language-model process is installed, so none was killed.

`python3 -m osamp demo` prints one local story: a wording task holds after repeated attempts, a sentence does not resume it, and the recovery record remains. Model calls recorded: 0.

## Known limitations

- No network, no second organization, and no Cameroon–Lagos pilot.
- No adopted signature, canonical wire format, or interoperability claim.
- Human approval is a local HMAC tag. The key is not stored; its hash is. This shows that an unsigned sentence is refused. It does not prove a person is present in a deployed identity system.
- The clock is supplied by the caller so tests stay repeatable. There is no trusted time source.
- A freeze has no lift operation. A human approval does not remove it.
- Default retention keeps the duty. Closure is either an authenticated terminate or a `close_when_due` flag that was in the original delegation.
- Numbers in `profile/local-draft-1` are placeholders. Changing them changes the fingerprint and requires a new acknowledgment.
- License for the code is not chosen in this submission.

## Questions for reviewers

1. Confirm Contract Zero stays a human schedule enforced by the covenant, not a sixth negotiated category.
2. What attempt, time, handoff, storage, and reminder numbers should each task class use? The current numbers are placeholders.
3. Where should the human approval key live so the agent process cannot present it?
4. Who may freeze authority, and what recorded review is allowed to lift a freeze?
5. Is a prior delegation enough to accept a bounded job, or is a fresh human tag required on every acceptance?
6. Is `close_when_due` an acceptable pre-agreed ending, or must a person press close even after that date?
7. Please leave the signature method, the backup location, and the numbered services 6–9 unset until you choose them. This slice blocks signature fields rather than guessing.
