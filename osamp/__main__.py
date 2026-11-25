"""Local commands. Nothing here opens a network connection."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from osamp.conformance import _accept, _boot, _offer, main as conformance_main
from osamp.errors import OsampError


def demo() -> int:
    print("Local demonstration on this computer only.")
    print("It does not send mail, and it does not connect one country to another.")
    print()
    with tempfile.TemporaryDirectory() as directory:
        node, keys = _boot(Path(directory))
        _offer(node)
        obligation_id = _accept(node)
        node.play(obligation_id)
        node.note_progress(obligation_id, None, cost=1)
        node.note_progress(obligation_id, None, cost=1)
        print(node.plain_status(obligation_id))
        print()
        try:
            node.natural_language_instruction(obligation_id, "just continue")
        except OsampError as exc:
            print(exc.plain)
        print()
        print("The recovery record is still here:")
        capsule = node.capsule(obligation_id)
        print(f"  work: {capsule['work_id']}")
        print(f"  objective: {capsule['objective']}")
        print(f"  human: {capsule['human_id']}")
        print(f"  blocker: {capsule['blocker']}")
        print()
        print(f"Model calls recorded: {node.model_calls()}")
        print("Operator key for this demo was kept in memory and was not a real identity.")
        print(f"Acknowledgment is present: {node.current_acknowledgment() is not None}")
        del keys
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] == "conformance":
        return conformance_main(args[1:])
    if args[0] == "demo":
        return demo()
    print("Use: python3 -m osamp conformance")
    print("Or:  python3 -m osamp demo")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
