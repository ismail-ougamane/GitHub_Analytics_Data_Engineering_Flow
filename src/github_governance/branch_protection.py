"""Branch protection: the API payload IS the acceptance criteria, encoded."""
from __future__ import annotations

from github_governance.settings import BranchProtectionSpec


def build_protection_payload(spec: BranchProtectionSpec) -> dict:
    """Body for PUT /repos/{owner}/{repo}/branches/{branch}/protection."""
    return {
        "required_status_checks": None,  # CI gates arrive in a later ticket
        "enforce_admins": spec.enforce_admins,
        "required_pull_request_reviews": {
            "required_approving_review_count": spec.required_approving_review_count,
            "dismiss_stale_reviews": spec.dismiss_stale_reviews,
            "require_code_owner_reviews": spec.require_code_owner_reviews,
            "require_last_push_approval": spec.require_last_push_approval,
        },
        "restrictions": None,
        "required_linear_history": spec.required_linear_history,
        "allow_force_pushes": spec.allow_force_pushes,
        "allow_deletions": spec.allow_deletions,
        "required_conversation_resolution": spec.required_conversation_resolution,
    }


def protection_matches(current: dict, desired: dict) -> bool:
    """Compare a GET /branches/{b}/protection response against a PUT payload.

    GET returns flags wrapped in {"enabled": bool}; PUT accepts bare booleans.
    """
    simple_flags = (
        "enforce_admins",
        "allow_force_pushes",
        "allow_deletions",
        "required_linear_history",
        "required_conversation_resolution",
    )
    for flag in simple_flags:
        actual = (current.get(flag) or {}).get("enabled")
        if actual is not desired[flag]:
            return False

    reviews = current.get("required_pull_request_reviews") or {}
    want_reviews = desired["required_pull_request_reviews"]
    if reviews is None and want_reviews:
        return False
    for key in (
        "required_approving_review_count",
        "dismiss_stale_reviews",
        "require_last_push_approval",
    ):
        if reviews.get(key) != want_reviews[key]:
            return False
    return True
