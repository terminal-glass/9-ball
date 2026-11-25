"""Stable fingerprints for records.

SHA-256 over sorted JSON is a local checksum. It is not a signature suite
and it does not prove who sent a message.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def key_hash(key: bytes) -> str:
    return "sha256:" + hashlib.sha256(key).hexdigest()
