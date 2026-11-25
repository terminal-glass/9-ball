"""Local limits and the governance fingerprint.

Numbers here are a draft profile for this copy of the software. They are not
a standard, and changing them changes the fingerprint a person acknowledged.
"""

from __future__ import annotations

from dataclasses import dataclass

from osamp.canonical import digest
from osamp.plain import OPERATOR_PROMISE

GOVERNANCE_VERSION = "covenant/local-draft-1"
PROTOCOL_LABEL = "osamp/0.8-draft"
PROFILE_ID = "profile/local-draft-1"

# Illustrative wire label from the paper. Not an interoperability claim.
WIRE_NOTE = (
    "protocol label osamp/0.8-draft is the paper's illustrative value, "
    "not a tested wire profile"
)

DEFAULT_LIMITS = {
    "max_attempts": 3,
    "max_same_progress": 2,
    "max_delegation_depth": 3,
    "max_reminders": 2,
    "reminder_gap_seconds": 3600,
    "max_open_obligations": 2,
    "storage_budget_bytes": 500_000,
    "max_payload_bytes": 65_536,
    "max_quarantine": 50,
    "lease_seconds": 3600,
    "retention_warning_seconds": 86_400,
    "max_delegation_budget": 100,
}

DEFAULT_TASK_CLASSES = ("public-wording",)


@dataclass(frozen=True)
class Profile:
    limits: dict
    allowed_task_classes: tuple[str, ...] = DEFAULT_TASK_CLASSES
    size: int = 1
    promise_text: str = OPERATOR_PROMISE
    governance_version: str = GOVERNANCE_VERSION
    profile_id: str = PROFILE_ID

    def material(self) -> dict:
        return {
            "governance_version": self.governance_version,
            "profile_id": self.profile_id,
            "size": self.size,
            "allowed_task_classes": list(self.allowed_task_classes),
            "limits": self.limits,
            "promise_text": self.promise_text,
            "controls": [
                "PLAY",
                "PAUSE",
                "STOP",
                "REWIND",
                "REVIEW",
                "FAST_FORWARD",
                "TIMEOUT",
            ],
            "contract_zero": True,
            "signature_suite": "not-adopted",
        }

    @property
    def governance_digest(self) -> str:
        return digest(self.material())


def default_profile(**overrides) -> Profile:
    limits = dict(DEFAULT_LIMITS)
    extra_limits = overrides.pop("limits", None)
    if extra_limits:
        limits.update(extra_limits)
    return Profile(limits=limits, **overrides)
