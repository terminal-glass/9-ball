# 9-ball

> **Looking for the Ollama model and hardware catalog? That's [8-ball](https://github.com/terminal-glass/8-ball).** 9-ball is the agentic build.

9-ball is a lightweight starting point for emergency-services help. The protocol underneath it is OSAMP, the Open Source Agent Mail Protocol.

This repository now contains a **local safety slice**. It can record a small accepted job, stop circular or stuck work, and keep a short recovery record on one computer. It does not send mail between countries, and it is not a running pilot.

## Start here if you are not an engineer

Read [OSAMP-Architecture.md](OSAMP-Architecture.md). It explains the parts, the three status boards, and how a safe hold works.

Then read `REVIEW-1.md` through `REVIEW-5.md`. Each note is one stage: five pieces, the tests, and the open questions.

## Folders and files

| Name | What it is |
| --- | --- |
| `osamp/` | The program: gate, covenant, Contract Zero, profile, and Postbox. |
| `tests/` | The checks reviewers can run. |
| `more/` | Older notes. The previous whitepaper PDF lives here. |
| `OSAMP-Architecture.md` | Plain-language architecture for this slice. |
| `REVIEW-1.md` | Review note for submission 1, the foundation. |
| `REVIEW-2.md` | Review note for stage 49-2, the five agreements. |
| `REVIEW-3.md` | Review note for stage 49-3, receipts, catch-up, and restore. |
| `REVIEW-4.md` | Review note for stage 49-4, data, retention, and security. |
| `REVIEW-5.md` | Review note for stage 49-5, acknowledgment, schedules, and crash recovery. |
| `OSAMP_Technical_Whitepaper_v0.82.txt` | Current technical draft, 24 November 2026. |
| `OSAMP_Contract_Outline_v0.1_2026-11-24.txt` | Current contract and implementation outline. |
| `OSAMP_Engineering_Introduction.pdf` | Older one-page brief from 17 November 2026. |
| `49.sh` | Linux controller. Runs `49-1.sh`, then later sub-stages, in order. |
| `49-1.sh` | Stage 49-1: Contract Zero and the foundation. |
| `49-2.sh` | Stage 49-2: Peer, Tribe, Clan, Table, and Work. |
| `49-3.sh` | Stage 49-3: receipts, catch-up, restore, and the check ledger. |
| `49-4.sh` | Stage 49-4: data, retention, and security schedules. |
| `49-5.sh` | Stage 49-5: acknowledgment, Project and Corridor schedules, a local measurement, and crash recovery. |
| `49-mac.sh` and `49-N-mac.sh` | The same groups for macOS. |
| `49-windows.ps1` and `49-N-windows.ps1` | The same groups for Windows. |
| `OSAMP-Linux`, `OSAMP-Mac`, `OSAMP-Windows` | Point at the stage 49 controller for that platform. |
| `OpenClaw-Installer-Linux`, `OpenClaw-Installer-Mac`, `OpenClaw-Installer-Windows` | Point at the same controllers. They do not install OpenClaw and they do not call stage 9. |

There is no `docs/` folder. Papers stay at the top so they are easy to find.

## Run the local checks

Python 3.12 or another current Python 3 is enough. No extra packages are required.

```text
python3 -m unittest discover -s tests -v
python3 -m osamp.conformance
python3 -m osamp demo
```

Stage 49 is the local controller. Its default is a dry run: it prints the groups and does not install packages or open a network connection.

```text
bash 49.sh --dry-run
bash 49.sh --status
bash 49-1.sh --verify
```

On Mac, `bash 49-mac.sh --dry-run` or `./OSAMP-Mac`. On Windows, run `OSAMP-Windows` or `OpenClaw-Installer-Windows` from a command prompt. Those names stay fixed. They hand off to `49-windows.ps1`.

## Current drafts and older paper

- [OSAMP Technical Whitepaper v0.82](OSAMP_Technical_Whitepaper_v0.82.txt) is the current protocol draft.
- [OSAMP Contract Outline v0.1](OSAMP_Contract_Outline_v0.1_2026-11-24.txt) is the current implementation outline.
- The previous whitepaper PDF, v0.81, is in [more/](more/).

A license for this code has not been chosen yet.
