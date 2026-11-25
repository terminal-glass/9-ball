# Review 6 — stage 49-6, shared vectors and a second small gate

This is installer stage **49-6**. `49.sh` runs it after 49-1 through 49-5.

| Platform | Controller | This group |
| --- | --- | --- |
| Linux | `49.sh` | `49-6.sh` |
| macOS | `49-mac.sh` | `49-6-mac.sh` |
| Windows | `49-windows.ps1` | `49-6-windows.ps1` |

```text
bash 49-6.sh --dry-run
bash 49-6.sh --status
bash 49-6.sh --verify
python3 -m osamp.trace
```

## The five pieces

1. **Shared envelope vectors.** `vectors.json` holds nine local cases: unknown sender, unknown event, signature field, bad checksum, admitted offer, expired offer, duplicate, changed body, and oversized payload.
2. **Independent adapter B.** `adapter-b.py` does not import the reference program. It also keeps a tiny hold record that stays stop-pending until the named peer confirms.
3. **Comparison.** The ledger runs both programs on those vectors and requires the same code.
4. **Requirement labels.** Every one of the 29 checks has a requirement id. `python3 -m osamp.trace` prints them. It does not itself claim a pass.
5. **Honest partial for WP-12.** Adapter B does not perform the other conformance checks, and a second organization did not run it. WP-12 stays partial. That is not an interoperability claim.

## Questions

1. Which vectors should a future second product have to pass before anyone may say "interoperable"?
2. Should adapter B stay one file at the top of this repository, or move only when a second maintainer owns it?
