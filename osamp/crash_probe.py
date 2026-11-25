"""Commit a hold, then wait so a test can kill the process.

Run as: python3 -m osamp.crash_probe <database> <ready-file> <obligation-id>
The hold is committed before the ready file is written.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from osamp.node import Node


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    database, ready, obligation_id = args
    node = Node.open(database)
    node.request_hold(obligation_id, "timeout", "Process crash check")
    Path(ready).write_text("ready", encoding="utf-8")
    time.sleep(60)
    node.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
