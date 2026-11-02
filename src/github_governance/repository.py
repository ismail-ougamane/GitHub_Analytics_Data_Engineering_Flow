"""Repository-level helpers (visibility, default branch)."""
from __future__ import annotations

from github_governance.collaborators import repo_path
from github_governance.settings import GovernanceConfig


def get_repository(client, config: GovernanceConfig) -> dict:
    return client.get(repo_path(config))


def ensure_visibility(client, config: GovernanceConfig) -> str | None:
    """Make the repo visibility match the spec; return a description or None."""
    repo = get_repository(client, config)
    desired_private = config.repository.visibility == "private"
    if bool(repo.get("private")) != desired_private:
        client.patch(repo_path(config), {"private": desired_private})
        return f"visibility set to {config.repository.visibility}"
    return None


def ensure_default_branch(client, config: GovernanceConfig) -> str | None:
    repo = get_repository(client, config)
    branch = config.branch_protection.branch
    if repo.get("default_branch") != branch:
        client.patch(repo_path(config), {"default_branch": branch})
        return f"default branch set to {branch}"
    return None
