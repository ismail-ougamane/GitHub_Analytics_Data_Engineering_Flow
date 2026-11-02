"""Idempotent convergence: running `apply` twice must not duplicate work and
must not leave drift (AC-4). Ordering matters: protection needs `main` to exist.
"""
from __future__ import annotations

import pytest

from github_governance.converge import apply_governance, plan_changes
from github_governance.errors import BranchMissingError, NotFoundError


@pytest.fixture
def converged_state(fake_client, config):
    """A repo with main@1 commit, no protection, no collaborators."""
    fake_client.state["branch_exists"] = True
    return fake_client


class TestPlan:
    def test_fresh_repo_lists_all_needed_actions(self, converged_state, config):
        actions = plan_changes(converged_state, config)
        kinds = {a.kind for a in actions}
        assert "protection" in kinds

    def test_repo_missing_raises_not_found(self, fake_client, config):
        fake_client.state["repo_missing"] = True
        with pytest.raises(NotFoundError):
            plan_changes(fake_client, config)


class TestApplyIdempotency:
    def test_apply_creates_protection(self, converged_state, config):
        apply_governance(converged_state, config)
        assert converged_state.state["protection"] is not None
        assert (
            converged_state.state["protection"]["required_pull_request_reviews"][
                "required_approving_review_count"
            ]
            == 1
        )

    def test_second_plan_is_empty(self, converged_state, config):
        apply_governance(converged_state, config)
        assert plan_changes(converged_state, config) == []

    def test_apply_never_reinvites_an_existing_collaborator(self, converged_state, config):
        converged_state.state["collaborators"] = [
            {"login": "already-in", "permissions": {"push": True}}
        ]
        apply_governance(converged_state, config)
        invite_calls = [
            c for c in converged_state.calls
            if c[0] == "PUT" and "/collaborators/already-in" in c[1]
        ]
        assert invite_calls == []

    def test_apply_is_safe_to_run_twice(self, converged_state, config):
        apply_governance(converged_state, config)
        before = dict(converged_state.state)
        apply_governance(converged_state, config)
        assert converged_state.state["protection"] == before["protection"]
        assert converged_state.state["invitations"] == before["invitations"]


class TestOrdering:
    def test_protection_requires_main_to_exist(self, fake_client, config):
        fake_client.state["branch_exists"] = False
        with pytest.raises(BranchMissingError, match="main"):
            apply_governance(fake_client, config)
        assert fake_client.state["protection"] is None
