# Review 5 — stage 49-5, acknowledgment, schedules, measurement, and crash recovery

This is installer stage **49-5**. `49.sh` runs it after 49-1 through 49-4.

| Platform | Controller | This group |
| --- | --- | --- |
| Linux | `49.sh` | `49-5.sh` |
| macOS | `49-mac.sh` | `49-5-mac.sh` |
| Windows | `49-windows.ps1` | `49-5-windows.ps1` |

```text
bash 49-5.sh --dry-run
bash 49-5.sh --status
bash 49-5.sh --verify
```

## The five pieces

1. **Human acknowledgment.** The recorded promise now says what stopping does not undo, that accepted work stays until closure, who may resolve a hold, and that installation or opening a file is not the acknowledgment. The stored digest covers that text.
2. **Project schedule.** A project needs an objective and at least one required check. The readable schedule also keeps exclusions, the budget, and who may accept completion.
3. **Corridor schedule.** The readable schedule lists the stages, the budget, and the stop rules: solved, human satisfied, held, or expired/closed.
4. **Local measured sample.** On first open, this computer hashes one fixed public sentence 2,000 times and records the date and the elapsed milliseconds. Only that bounded step fits. A whole project is refused. This is not a laboratory 1–9 ranking.
5. **Killed process.** A child process commits a hold, then the operating system kills it. The hold is still there and PLAY is refused. The machine stayed powered on.

## Ledger change

WP-04 and CZ-28 move to pass. WP-04's evidence names the local sample and says it is not a cross-vendor benchmark. CZ-28's evidence says the power cord was not pulled.

## Questions

1. Is hashing one public sentence an acceptable published sample until you choose a real task-class benchmark?
2. Do you want the acknowledgment shown on screen and confirmed with a key that this program cannot see, before any further work?
