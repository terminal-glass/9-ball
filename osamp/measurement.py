"""One local timing sample for the published profile.

The sample is a fixed public sentence hashed on this computer. It is not a
laboratory benchmark and it does not rank a person.
"""

from __future__ import annotations

import hashlib
import time

SAMPLE_TEXT = b"Please tighten one public sentence about rain."


def measure(measured_at: str) -> dict:
    started = time.perf_counter()
    digest = ""
    for _ in range(2000):
        digest = hashlib.sha256(SAMPLE_TEXT).hexdigest()
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    return {
        "task_class": "public-wording",
        "subtask_id": "sentence-1",
        "scope": "bounded",
        "measured_at": measured_at,
        "elapsed_ms": elapsed_ms,
        "sample": "sha256 of one fixed public sentence, repeated 2000 times",
        "sample_digest": digest,
        "size": 1,
    }
