"""AC-1: the repository exists, is public, and `main` is the default branch."""
from __future__ import annotations

import pytest


@pytest.mark.live
def test_repository_exists_and_is_configured(live_client, config):
    repo = live_client.get(f"/repos/{config.repository.owner}/{config.repository.name}")

    assert repo["full_name"] == f"{config.repository.owner}/{config.repository.name}", (
        "repository must exist under the expected owner"
    )
    assert repo["default_branch"] == "main", (
        "protection on `main` is meaningless if it is not the default branch"
    )
    assert repo["private"] is False, (
        "decision D1: GitHub Free cannot protect private branches, "
        "so the repository must be public"
    )
    assert repo["visibility"] == "public"


@pytest.mark.live
def test_main_branch_has_at_least_one_commit(live_client, config):
    """Branch protection requires the branch to exist with history."""
    commits = live_client.get(
        f"/repos/{config.repository.owner}/{config.repository.name}/commits"
    )
    assert len(commits) >= 1, "`main` must have at least one commit before protection"
