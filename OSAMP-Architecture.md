# OSAMP architecture

A plain-language guide for the first local slice. 24 November 2026.

This paper is for people who need to understand the software without an information-technology background. The technical drafts are `OSAMP_Technical_Whitepaper_v0.82.txt` and `OSAMP_Contract_Outline_v0.1_2026-11-24.txt`.

## Where this sits

In the installer line this work is stage 49, the 9-Ball controller. This repository keeps the release-folder shape: `49.sh` calls `49-1.sh`, then any later `49-2.sh` and so on. macOS and Windows have matching entry files. Nothing here calls stage 9, and this copy has not been placed into the separate installer repository.

## What this is

OSAMP is the Open Source Agent Mail Protocol. It is the rule book behind 9-Ball: how separately owned helpers may contact each other, accept a limited job, stop, and keep a record a person can read.

The aim is social, networking, and humanitarian work. Safety, a human decision, and a record that survives a restart come before speed or automation.

This repository currently holds a **local slice**. It runs on one computer. It can accept a small job, notice circular or stuck work, hold that work, and keep a short recovery record. It does not send mail to another computer. It does not show that Cameroon, Lagos, Madrid, or the United States are connected. Those places appear in the whitepaper as a proposed pilot, not as a running service.

## The five pieces in this slice

1. **Contract Zero — human oversight and safe hold.** Before work starts, a named person acknowledges the safeguards. If work loops, repeats one source as if it were several checks, or makes no progress, the computer holds that work and asks a designated person. Silence does not restart it.
2. **The covenant and three status boards.** The built-in rules are PLAY, PAUSE, STOP, REWIND, REVIEW, FAST-FORWARD, and TIMEOUT. Delivery, permission, and execution are three separate boards.
3. **The Postbox.** One local database stores offers, accepted duties, receipts, holds, and notices. Throwing away an unanswered invitation does not throw away an accepted duty.
4. **The gate.** Ordinary code checks the sender, the message type, the size, and duplicates before any tool runs. A language model is not asked to make that decision.
5. **The local profile.** This copy publishes its own limits: how many tries, how deep a handoff may go, how much it will store, and how long a running permit lasts. Changing those limits requires the person to acknowledge them again.

Contract Zero is not a sixth kind of agreement. The five negotiated kinds remain Peer, Tribe, Clan, Table, and Work. Submission 2 records those five on this same computer. Accepting one does not grant the powers of another. A bridge approval queues a local note. It still does not transmit anything.

## The parts, in everyday words

| Part | What a person can think of it as | What it does on this computer |
| --- | --- | --- |
| Gate | The door check | Decides whether a message may even sit in the inbox. Unknown senders stay in quarantine. |
| Covenant | The house rules | Blocks start, tools, and shortcuts when a hold, a stop, a spent budget, or a missing acknowledgment is in force. |
| Postbox | The filing cabinet | Keeps the duty after the program stops. One SQLite file. |
| Profile | The posted limits | Says what this small worker may accept. A bigger machine would not gain more authority. |
| Contract Zero | The duty to stop and ask | Writes the recovery record and waits for the designated person. |
| Launch scripts | A way to run the checks | `OSAMP-Linux`, `OSAMP-Mac`, and `OSAMP-Windows` run the local checks. They do not install a mail service. |

The OpenClaw installer files stay in the repository under their existing names. This slice does not change them and does not install OpenClaw.

## Three status boards that must not be mixed

A message can have arrived, and still be waiting for a yes. A yes can exist while the work is held. A held job can exist while the other computer has not confirmed a stop.

| Board | Question it answers | Example values |
| --- | --- | --- |
| Delivery | Did the message arrive in this inbox? | queued, delivered, expired, failed |
| Authority | Did someone accept this role? | offered, accepted, revoked, closed |
| Execution | What is the work doing now? | ready, working, held, review, stop pending, stopped, uncertain, completed, closed |

`STOP_PENDING` means a stop was requested and the responsible computer has not confirmed it. Time passing does not turn that into "stopped."

Completion is a later record. A hold remains in the history. Closing a job is not the same as calling it successful.

## Transport stays separate from trust

The meaning of a message is the signed agreement and the local decision, not the pipe that carried it. Email, a web connection, or another agent tool could carry the same record later. This slice has no pipe. Arriving in the local inbox is not permission to work. A sentence in the message is not a decision. A field named signature is refused, because no signature method has been chosen yet.

## Safe hold and recovery

The recovery record is written in the same save as the acceptance. If that save fails, the computer does not say the job was accepted.

The record keeps the job name, the role, the contract fingerprint, the objective, the limits, the designated person, what has been done, known outside effects, the blocker, the budget, and the decision being asked. It does not keep a full conversation or private reasoning.

On a hold, the program stops new model calls, tools, and handoffs for that job. Other unrelated accepted jobs may continue. The hold can be widened only by an authenticated local approval.

A smaller worker uses the same rules. If there is not enough space for the recovery record, the new job is refused. Jobs already accepted stay on file. None of this needs a language model to be running. This copy does not include a language model at all.

Resuming a confusion or loop hold takes a tagged decision from the designated person or the named deputy. The tag is a local approval mark. The software then checks acknowledgment, budget, holds, and blocks again. The approval does not reset the money or the attempt count, does not add a sender, and does not lift a freeze.

If a human never answers, the default is to keep the duty. A closure happens only when the original delegation said `close_when_due` and the retention time has passed, or when the person chooses terminate. The objective text is then removed from this one file. A short disposition remains. There is no backup system in this slice, so copies outside this file are a known gap.

## Why Python and SQLite

The program is Python 3, using only the standard library, and SQLite, which Python already includes.

- The same text runs on Windows, Mac, and Linux.
- There is no package to download and no account to create.
- The filing cabinet is one file. It works with the network unplugged.
- A save is finished before acceptance is reported. Tests include a save that fails on purpose and leaves no duty behind.
- The safety rules are ordinary code, so they still run when no language model is installed.
- A reviewer can read the files in `osamp/` without learning a framework.

This is a draft profile called `covenant/local-draft-1`. The numbers in it are placeholders, not a standard. The wire label `osamp/0.8-draft` is the whitepaper's example name, not a tested common format.

## What this slice does not do

- It does not exchange live messages with a second organization.
- It records Peer, Tribe, Clan, Table, and Work on this computer. It does not deliver them to another computer.
- It does not verify cryptographic signatures. Unknown security choices were left blocked rather than invented.
- It does not measure a real 1–9 capability benchmark.
- It does not delete backups, because it does not make backups.
- It does not cut power on a machine. Restart tests close and reopen the file.
- It does not claim endorsement by OpenClaw, xAI, Grok, or any community group.

## Requirement to code and test

Statuses below are from `python3 -m osamp.conformance` and `python3 -m unittest discover -s tests -v` on this slice. Pass means the named local behavior ran. Partial means part of the check ran and the rest is named. Pending means the code for that check is not in this submission.

| Requirement | Plain meaning | Code | Test | Status |
| --- | --- | --- | --- | --- |
| P-Z01, P-Z02, CZ-22 | Acknowledge safeguards before work. Acknowledgment is not a job and not a contact list. | `osamp/node.py` acknowledgment and delegation | CZ-22 | Pass |
| P-Z03, B-EVID01, CZ-23, WP-19 | Repeated use of one source is not independent confirmation. | `osamp/contract_zero.py` | CZ-23, WP-19 | Pass |
| P-Z03, CZ-24 | Attempt limits and circular handoffs stop without a model, and do not renew the budget. | `osamp/contract_zero.py` | CZ-24 | Pass |
| P-Z04, P-Z05, B-CTRL01 | Hold, pause, and stop block tools. The filing cabinet still answers. | `osamp/covenant.py`, `osamp/node.py` | WP-17, WP-21 | Pass |
| P-Z07, B-RET01, WP-03 | Acceptance and the recovery record are saved together and survive reopening the file. | `osamp/postbox.py`, `osamp/node.py` | WP-03 | Pass |
| P-Z08, CZ-25 | A small store can hold with no model, and refuses a job it cannot record. | `osamp/profile.py`, `osamp/node.py` | CZ-25 | Pass |
| P-Z10, P-Z11, CZ-26 | Notices have their own queued, sent, and delivered states. Silence leaves the duty in place. | `osamp/node.py` | CZ-26 | Pass |
| P-Z12, P-Z13, CZ-27 | A tagged decision from the designated person or deputy is required. Spend and senders stay as they were. | `osamp/auth.py`, `osamp/node.py` | CZ-27 | Pass |
| B-CTRL02, WP-09, WP-17 | A remote stop stays STOP_PENDING until the named confirmation. | `osamp/node.py`, `osamp/plain.py` | WP-09, WP-17 | Pass, local record only |
| B-GATE02, WP-01, WP-02 | Unknown senders are not forwarded. An unanswered invitation does not use a model. | `osamp/gate.py` | WP-01, WP-02 | Pass, allowlist rather than signatures |
| P-MSG04, WP-07 | The same message id does not accept twice. A changed body under that id is refused. | `osamp/gate.py`, `osamp/postbox.py` | WP-07, foundation concurrency test | Pass |
| B-QUEUE01, WP-08 | Reopening the file still enforces holds and revocation. | `osamp/postbox.py` | WP-08 | Pass for reopening this file |
| B-QUEUE04, WP-10 | Expired invitation text is removed from this file. Accepted text stays. | `osamp/node.py` compact | WP-10 | Partial: no backup store |
| B-CTRL01, WP-18, WP-20 | Rewind keeps history and outside effects. Fast-forward cannot skip a yes or a hold. | `osamp/covenant.py` | WP-18, WP-20 | Pass |
| B-AUTH01, WP-21 | Switching off the covenant withdraws any conformance claim. | `osamp/node.py` | WP-21 | Pass |
| B-CAP01, WP-04 | A bounded step can be named. A whole project is refused. | `osamp/contract_zero.py` | WP-04 | Partial: no measured benchmark |
| B-COR02, WP-16 | Holds and a human-satisfied receipt stay on file. | `osamp/node.py`, `osamp/agreements.py` | WP-16 | Pass |
| CZ-28 | Restart keeps uncertain outside effects and does not repeat them. | `osamp/node.py` | CZ-28 | Partial: no power cut, no backup restore |
| P-Z09, CZ-29 | Retention notice and agreed closure remove only the eligible objective from this file. | `osamp/node.py` | CZ-29 | Partial: no off-site copies |
| B-TRIBE01, WP-05 | Tribe help has its own budget. Membership is not a job. | `osamp/agreements.py` | WP-05 | Pass, local queue only |
| B-CLAN01, WP-06 | A bridge needs a human approval. An endorsement does not open a route. | `osamp/agreements.py` | WP-06 | Pass, nothing transmitted |
| B-DATA02, WP-11 | Catch-up shows only the authorized minimum. | — | WP-11 | Pending |
| B-MSG05, WP-12 | A second implementation passes the same checks. | — | WP-12 | Pending |
| B-TABLE01, WP-13 | Sitting at a Table requires an accepted role. | `osamp/agreements.py` | WP-13 | Pass |
| B-AUTH01, WP-14 | The five agreements do not grant each other's powers. | `osamp/agreements.py` | WP-14 | Pass |
| B-COR01, B-COR02, WP-15 | A Corridor follows its stages, stops when solved, and does not reset its budget. | `osamp/agreements.py` | WP-15 | Pass |
| B-WORK01 | A project completes only when its required checks passed. | `osamp/agreements.py` | `tests/test_agreements.py` | Pass for that local rule |

The commands that produced this table are:

```text
python3 -m unittest discover -s tests -v
python3 -m osamp.conformance
```

On the run recorded after submission 2: 10 unit tests OK; conformance totals 23 pass, 4 partial, 2 pending, 0 fail.
