"""AC-2: `main` requires a pull request with at least 1 approval."""
from __future__ import annotations

import pytest


@pytest.mark.live
def test_main_requires_a_pull_request_with_at_least_one_approval(live_client, config):
    protection = live_client.get(
        f"/repos/{config.repository.owner}/{config.repository.name}/branches/main/protection"
    )

    reviews = protection.get("required_pull_request_reviews")
    assert reviews is not None, (
        "AC-2 violated: merging into main does not require pull request reviews"
    )
    assert reviews["required_approving_review_count"] >= 1, (
        "AC-2 violated: at least 1 approving review must be required"
    )
    assert reviews["dismiss_stale_reviews"] is True, (
        "new commits after an approval must dismiss the approval"
    )
    assert reviews["require_last_push_approval"] is True, (
        "the latest push must be reviewable, otherwise someone can approve "
        "and then sneak in new commits"
    )


@pytest.mark.live
def test_protection_cannot_be_bypassed_by_admins(live_client, config):
    protection = live_client.get(
        f"/repos/{config.repository.owner}/{config.repository.name}/branches/main/protection"
    )
    assert protection["enforce_admins"]["enabled"] is True, (
        "AC-3 violated: repository admins can bypass the review requirement"
    )
