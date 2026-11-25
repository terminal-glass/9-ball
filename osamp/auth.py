"""Local tags for human decisions.

The node stores a hash of a person's key, not the key. The person must present
the key again to approve a decision. This is a local stand-in so an unsigned
sentence can be rejected. It is not the OSAMP wire signature suite, which is
still an open choice.
"""

from __future__ import annotations

import hmac
import hashlib
from typing import Any

from osamp.canonical import canonical_bytes


def mac(key: bytes, payload: dict[str, Any]) -> str:
    return hmac.new(key, canonical_bytes(payload), hashlib.sha256).hexdigest()


def mac_ok(key: bytes, payload: dict[str, Any], presented: str) -> bool:
    if not isinstance(presented, str) or not presented:
        return False
    return hmac.compare_digest(mac(key, payload), presented)
