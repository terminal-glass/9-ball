"""Sentences an operator can read without a technical background."""

from __future__ import annotations

OPERATOR_PROMISE = (
    "You remain responsible for the authority you give this system. "
    "It may decline new work or stop accepted work when it lacks evidence, "
    "capacity, permission, or a safe next step. If it gets stuck, repeats "
    "an unsupported conclusion, or passes work in circles, it must pause "
    "that work and ask an authorized person for help. It must keep a short "
    "recovery record for accepted work. Silence, a timeout, a stronger "
    "model, and agreement among helpers do not authorize it to continue."
)

HOLD_SENTENCES = {
    "copied_source": (
        "Several helpers repeated one source and treated it as separate "
        "confirmation. That is not independent checking."
    ),
    "circular_delegation": (
        "This work was passed around and came back without a new, approved step."
    ),
    "conflicting_evidence": (
        "The records disagree, and the accepted role cannot safely choose."
    ),
    "no_progress": (
        "The same attempt was repeated without new evidence, or the attempt "
        "limit was reached."
    ),
    "missing_checkpoint": (
        "The last safe checkpoint or the authority for this work cannot be "
        "reconstructed."
    ),
    "capacity_pressure": (
        "There is not enough saved space to protect accepted work."
    ),
    "timeout": "The time limit was reached. Waiting is not the same as success.",
    "integrity_failure": "A stored record did not match its check value.",
    "compromised_authority": (
        "The authority for this scope is frozen until a person reviews it."
    ),
    "operator_pause": "A person paused this work.",
    "remote_stop": "A stop was requested and is not yet confirmed.",
    "lease_expired": "The work permit timed out and was not renewed.",
    "retention": "The retention deadline is near. A person must choose what to keep.",
}

PERMITTED_HUMAN_STEPS = (
    "leave_held",
    "terminate",
    "clarify",
    "approve_same_step",
)


def hold_sentence(reason: str) -> str:
    return HOLD_SENTENCES.get(reason, "This work is held for a recorded reason.")
