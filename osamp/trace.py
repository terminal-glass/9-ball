"""Print the requirement names next to each conformance check.

The live pass or pending result still comes from python3 -m osamp.conformance.
"""

from __future__ import annotations

from osamp.conformance import CHECKS, REQUIREMENTS


def lines() -> list[str]:
    output = []
    for check_id, title, _fn in CHECKS:
        output.append(f"{check_id}  {REQUIREMENTS[check_id]}  {title}")
    return output


def main() -> int:
    print("OSAMP requirement trace. This list does not by itself say which checks passed.")
    print("Run python3 -m osamp.conformance for the live ledger.")
    print("This is one computer. It is not a federation test.")
    print()
    for line in lines():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
