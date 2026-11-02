"""Collaborator invitations (AC-1: every colleague has write access)."""
from __future__ import annotations

from github_governance.settings import CollaboratorSpec, GovernanceConfig


def repo_path(config: GovernanceConfig) -> str:
    return f"/repos/{config.repository.owner}/{config.repository.name}"


def ensure_collaborator(
    client, config: GovernanceConfig, collaborator: CollaboratorSpec
) -> str:
    """PUT /collaborators/{login} — 201 = invitation created, 204 = already in."""
    response = client.put(
        f"{repo_path(config)}/collaborators/{collaborator.login}",
        {"permission": collaborator.permission},
    )
    if "login" in response:
        return f"invited {collaborator.login} ({collaborator.permission})"
    return f"{collaborator.login} already has access ({collaborator.permission})"
