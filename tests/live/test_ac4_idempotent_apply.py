"""AC-4: the applied governance state is stable — planning twice yields no
drift, and the protection that exists matches config/governance.toml exactly.
"""
from __future__ import annotations

import pytest

from github_governance.branch_protection import protection_matches
from github_governance.converge import plan_changes


@pytest.mark.live
def test_governance_is_fully_converged(live_client, config):
    """`plan` must report zero actions on a converged repository."""
    drift = plan_changes(live_client, config)
    assert drift == [], "governance drift detected:\n" + "\n".join(
        f"- [{a.kind}] {a.detail}" for a in drift
    )


@pytest.mark.live
def test_live_protection_matches_the_configured_spec(live_client, config):
    from github_governance.branch_protection import build_protection_payload

    desired = build_protection_payload(config.branch_protection)
    current = live_client.get(
        f"/repos/{config.repository.owner}/{config.repository.name}/branches/main/protection"
    )
    assert protection_matches(current, desired), (
        f"live protection drifted from config:\n{current}"
    )
