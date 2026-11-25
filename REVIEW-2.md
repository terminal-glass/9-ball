# Review 2 — stage 49-2, Peer, Tribe, Clan, Table, and Work

This is installer stage **49-2**. `49.sh` calls `49-1.sh` first, then `49-2.sh`. Read `REVIEW-1.md` for stage 49-1. This note covers only the five negotiated agreements.

| Platform | Controller | This group |
| --- | --- | --- |
| Linux | `49.sh` | `49-2.sh` |
| macOS | `49-mac.sh` | `49-2-mac.sh` |
| Windows | `49-windows.ps1` | `49-2-windows.ps1` |

```text
bash 49-2.sh --dry-run
bash 49-2.sh --status
bash 49-2.sh --verify
bash 49.sh --dry-run
```

Nothing was transmitted. A queued bridge note is a row in the local database. It is not a message to Lagos, Madrid, or anywhere else. Do not merge until Jonathan gives an explicit go-ahead.

## The five pieces

1. **Peer.** A human accepts a named owner, key id, message types, and data classes. Receipt of mail does not accept the peer. A revoked peer is refused. An endorsement does not accept the peer.
2. **Tribe.** Members, a help budget, and a declined list. Membership creates no job. Spending the budget does not renew it. A refusal is not followed by another ask.
3. **Clan and bridge.** Destinations and a hop limit are fixed at acceptance. A new peer does not inherit them. Crossing to an unnamed destination needs a separate human-approved bridge. The bridge queues a local note and does not transmit.
4. **Table.** An invitation does not seat a participant. An accepted role survives reopening the file, does not open another table, and is not released by a proposed handoff.
5. **Work.** A Project completes only when every required check passed. A Corridor offers only the current stage, stops when solved, does not reset spend when a stage is repeated, holds if a stage goes backwards, and does not add a recipient when a stage is declined. `HUMAN_SATISFIED` is a durable receipt.

Code: `osamp/agreements.py`. Checks: `tests/test_agreements.py` and the conformance entries named below.

## Requirement to code and test

| Piece | Requirements | Checks |
| --- | --- | --- |
| Peer | B-PEER01, B-ID03 | `test_revoked_peer_and_narrow_message_type_fail_closed`; endorsement covered by WP-06 |
| Tribe | B-TRIBE01, P-CAP03 | WP-05 pass |
| Clan and bridge | B-CLAN01, B-DATA01 | WP-06 pass, with transmitted=false |
| Table | B-TABLE01, B-TABLE02 | WP-13 pass |
| Work | B-WORK01, B-COR01, B-COR02 | WP-15 pass; project checks in `test_project_completion_needs_every_check`; WP-16 pass for human satisfaction |

WP-14 pass shows the five scopes do not grant each other.

## Test evidence

Commands, Python 3.12.3:

```text
python3 -m unittest discover -s tests -v
python3 -m osamp.conformance
```

Result: **10 unit tests, all OK.** Conformance: **23 pass, 4 partial, 2 pending, 0 fail.**

Newly passing in this submission: WP-05, WP-06, WP-13, WP-14, WP-15, and WP-16 (it was partial).

Still partial: WP-04, WP-10, CZ-28, CZ-29. Still pending: WP-11 catch-up, WP-12 a second implementation.

## Known limitations

- No bytes leave this computer. `escalate` returns `transmitted: false`.
- Peer identity is still the local allowlist plus an agreement row. There is no signature suite.
- Bridge expiry uses the caller-supplied clock.
- A handoff proposal does not move the role. This slice also does not complete a handoff by seating the recipient. That remains an open step.
- Corridor stages are records. They do not call a tool or a model.
- Fixture names such as `dest-known` are not places, partners, or a pilot.

## Questions for reviewers

1. Is a bridge allowed to name a destination that was not in the original clan list, as this slice does, or must the clan be amended first?
2. Should a proposed handoff stay incomplete until the recipient accepts and the original person releases it? This slice only records the proposal.
3. Are the project checks a list of names supplied by the human, or do they need to be tied to artifacts?
4. Confirm that tribe, clan, and table acceptance still require the Contract Zero acknowledgment from submission 1. They do in this code, because work acceptance goes through that gate. Simply recording a peer or tribe does not start execution.
