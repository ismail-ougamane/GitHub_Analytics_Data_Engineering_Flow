"""AC-3: direct pushes to `main` are blocked — for everyone, admins included,
and history cannot be rewritten to smuggle unreviewed changes in.
"""
from __future__ import annotations

import pytest


@pytest.mark.live
def test_direct_pushes_are_blocked_including_for_admins(live_client, config):
    protection = live_client.get(
        f"/repos/{config.repository.owner}/{config.repository.name}/branches/main/protection"
    )

    # A PR gate alone is not enough: without `enforce_admins` the owner can
    # still push straight to main, making AC-3 cosmetic.
    assert protection["enforce_admins"]["enabled"] is True, (
        "direct pushes must be blocked for admins too"
    )
    assert protection["required_pull_request_reviews"] is not None, (
        "a PR must be the only path into main"
    )
    assert protection["allow_force_pushes"]["enabled"] is False, (
        "force pushes would allow rewriting reviewed history"
    )
    assert protection["allow_deletions"]["enabled"] is False, (
        "`main` must not be deletable"
    )
