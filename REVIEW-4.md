# Review 4 — stage 49-4, data, retention, and security

This is installer stage **49-4**. `49.sh` runs it after 49-1, 49-2, and 49-3.

| Platform | Controller | This group |
| --- | --- | --- |
| Linux | `49.sh` | `49-4.sh` |
| macOS | `49-mac.sh` | `49-4-mac.sh` |
| Windows | `49-windows.ps1` | `49-4-windows.ps1` |

```text
bash 49-4.sh --dry-run
bash 49-4.sh --status
bash 49-4.sh --verify
```

## The five pieces

1. **Data schedule.** `public-example`, `metadata-only`, and `private-medical` are named. A private-medical placeholder stays off public-news and press routes.
2. **Retention schedule.** An unanswered invitation loses its body at expiry. Accepted work stays until an explicit closure. The schedule says off-site backups are none.
3. **Local backup deletion.** A second file, `*.backup`, receives the same invitation text and the same objective. Expiry and closure clear the eligible text there too, then the file is compacted.
4. **Security schedule.** Help notices cannot carry a field named secret, password, token, or API key. Tools stay on the accepted allowlist. A signature field is still not proof.
5. **Traceability.** `trace_rows()` names B-DATA01, B-QUEUE04, B-SEC01, and P-Z09.

## Ledger change

WP-10 and CZ-29 move from partial to pass for the declared local copies: the main database, its audit rows, and the local backup file. The pass states that no off-site backup exists, so none was deleted.

## Questions

1. Is one local backup file the retention scope you want recorded, or do you want a second directory named by the operator?
2. Should a notice be blocked only when a field is named `password`, or also when the word appears in a sentence?
