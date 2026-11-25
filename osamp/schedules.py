"""Local data, retention, and security schedules.

These are the rules this copy enforces. They are not a claim about another
computer's copies.
"""

from __future__ import annotations

from osamp.errors import OsampError

DATA_CLASSES = {
    "public-example": "May be shown on a review route or a public-news route.",
    "metadata-only": "May be shown on a review route. It is not a document body.",
    "private-medical": "May be shown only on a designated review route. It stays off public news and press routes.",
}

RETENTION = {
    "unaccepted_invitation": "Delete the body when the offer expires. Keep the event id.",
    "accepted_work": "Keep the obligation until an explicit closure.",
    "hold_and_closure": "Keep the disposition. Delete the objective text on closure.",
    "offsite_backups": "None are declared. This copy cannot delete a copy it does not have.",
}

SECURITY = {
    "content": "Message text is data, even from a known sender.",
    "tools": "A tool runs only when it is on the accepted allowlist and the work is running.",
    "notices": "A help notice must not carry a secret, password, token, or API key.",
    "signatures": "A signature field is not proof until a signature method is adopted.",
}

FORBIDDEN_NOTICE_KEYS = frozenset({"secret", "password", "token", "api_key"})


def allow_route(data_class: str, route: str) -> None:
    if data_class not in DATA_CLASSES:
        raise OsampError("data_refused", "That data class is not in the local schedule.")
    if data_class == "private-medical" and route in {"public-news", "press"}:
        raise OsampError(
            "catchup_refused",
            "A private medical note stays off public and press routes.",
        )
    if data_class == "metadata-only" and route in {"public-news", "press"}:
        raise OsampError("data_refused", "Metadata-only material stays off public and press routes.")


def screen_notice(body: dict) -> None:
    keys = _keys(body)
    found = FORBIDDEN_NOTICE_KEYS.intersection(keys)
    if found:
        raise OsampError(
            "notice_refused",
            "A help notice cannot carry a secret, password, token, or API key.",
        )


def _keys(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            found.add(str(key))
            found.update(_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_keys(item))
    return found


def trace_rows() -> list[tuple[str, str, str]]:
    return [
        ("B-DATA01", "Data classes and routes", "osamp/schedules.py allow_route"),
        ("B-QUEUE04", "Deletion across the main file and the local backup", "osamp/postbox.py copies"),
        ("B-SEC01", "Notices stay free of secrets and tools stay on an allowlist", "osamp/schedules.py screen_notice"),
        ("P-Z09", "Closure keeps a disposition and deletes eligible objective text", "osamp/node.py _close_obligation"),
    ]
