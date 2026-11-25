# 9-ball

> **Looking for the Ollama model and hardware catalog? That's [8-ball](https://github.com/terminal-glass/8-ball).** 9-ball is the agentic build.

9-ball is a lightweight starting point for emergency-services help. The protocol underneath it is OSAMP, the Open Source Agent Mail Protocol.

This repository now contains a **local safety slice**. It can record a small accepted job, stop circular or stuck work, and keep a short recovery record on one computer. It does not send mail between countries, and it is not a running pilot.

## Start here if you are not an engineer

Read [OSAMP-Architecture.md](OSAMP-Architecture.md). It explains the parts, the three status boards, and how a safe hold works.

Then read [REVIEW-1.md](REVIEW-1.md). It says what the first submission contains, what the tests showed, and what still needs a human decision.

## Folders and files

| Name | What it is |
| --- | --- |
| `osamp/` | The program: gate, covenant, Contract Zero, profile, and Postbox. |
| `tests/` | The checks reviewers can run. |
| `more/` | Older notes. The previous whitepaper PDF lives here. |
| `OSAMP-Architecture.md` | Plain-language architecture for this slice. |
| `REVIEW-1.md` | Review note for submission 1. |
| `OSAMP_Technical_Whitepaper_v0.82.txt` | Current technical draft, 24 November 2026. |
| `OSAMP_Contract_Outline_v0.1_2026-11-24.txt` | Current contract and implementation outline. |
| `OSAMP_Engineering_Introduction.pdf` | Older one-page brief from 17 November 2026. |
| `OSAMP-Linux`, `OSAMP-Mac`, `OSAMP-Windows` | Run the local checks. They do not install network mail. |
| `OpenClaw-Installer-Windows`, `OpenClaw-Installer-Mac`, `OpenClaw-Installer-Linux` | Kept under these names. This slice does not fill or run them. |

There is no `docs/` folder. Papers stay at the top so they are easy to find.

## Run the local checks

Python 3.12 or another current Python 3 is enough. No extra packages are required.

```text
python3 -m unittest discover -s tests -v
python3 -m osamp.conformance
python3 -m osamp demo
```

On Mac or Linux you can also run `./OSAMP-Mac` or `./OSAMP-Linux`. On Windows, run `OSAMP-Windows` from a command prompt in this folder, or run the `python` command above. The Windows file is a command script without a `.bat` suffix because the name had to stay `OSAMP-Windows`.

## Current drafts and older paper

- [OSAMP Technical Whitepaper v0.82](OSAMP_Technical_Whitepaper_v0.82.txt) is the current protocol draft.
- [OSAMP Contract Outline v0.1](OSAMP_Contract_Outline_v0.1_2026-11-24.txt) is the current implementation outline.
- The previous whitepaper PDF, v0.81, is in [more/](more/).

A license for this code has not been chosen yet.
