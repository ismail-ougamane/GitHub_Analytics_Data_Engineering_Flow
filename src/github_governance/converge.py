"""Converge the real repository to config/governance.toml.

`plan_changes` is read-only (drift report); `apply_governance` executes the
plan. Both are idempotent: on a converged repository the plan is empty.
"""
from __future__ import annotations

from dataclasses import dataclass

from github_governance.branch_protection import build_protection_payload, protection_matches
from github_governance.collaborators import ensure_collaborator, repo_path
from github_governance.errors import BranchMissingError, NotFoundError
from github_governance.repository import ensure_default_branch, ensure_visibility
from github_governance.settings import GovernanceConfig


@dataclass(frozen=True)
class Action:
    kind: str  # visibility | default_branch | collaborator | protection
    target: str
    detail: str

    def __repr__(self) -> str:
        return f"[{self.kind}] {self.detail}"


def plan_changes(client, config: GovernanceConfig) -> list[Action]:
    """Compare desired state against live state. Read-only."""
    repo = client.get(repo_path(config))
    actions: list[Action] = []
    target = repo.get("full_name", f"{config.repository.owner}/{config.repository.name}")

    desired_private = config.repository.visibility == "private"
    if bool(repo.get("private")) != desired_private:
        actions.append(
            Action("visibility", target, f"set visibility to {config.repository.visibility}")
        )

    if repo.get("default_branch") != config.branch_protection.branch:
        actions.append(
            Action(
                "default_branch",
                target,
                f"set default branch to {config.branch_protection.branch}",
            )
        )

    collaborators = client.get(f"{repo_path(config)}/collaborators")
    existing = {c["login"] for c in collaborators}
    invitations = client.get(f"{repo_path(config)}/invitations")
    invited = {i["login"] for i in invitations}
    for collab in config.collaborators:
        if collab.login not in existing and collab.login not in invited:
            actions.append(
                Action(
                    "collaborator",
                    collab.login,
                    f"invite {collab.login} with permission '{collab.permission}'",
                )
            )

    branch = config.branch_protection.branch
    try:
        current = client.get(f"{repo_path(config)}/branches/{branch}/protection")
    except NotFoundError:
        actions.append(
            Action("protection", branch, f"create branch protection for {branch}")
        )
    else:
        if not protection_matches(current, build_protection_payload(config.branch_protection)):
            actions.append(
                Action("protection", branch, f"update drifted branch protection for {branch}")
            )

    return actions


def apply_governance(client, config: GovernanceConfig) -> list[Action]:
    """Execute the plan. Returns the actions that were applied."""
    actions = plan_changes(client, config)
    if not actions:
        return []

    for action in actions:
        if action.kind == "visibility":
            ensure_visibility(client, config)
        elif action.kind == "default_branch":
            ensure_default_branch(client, config)
        elif action.kind == "collaborator":
            collaborator = next(c for c in config.collaborators if c.login == action.target)
            ensure_collaborator(client, config, collaborator)
        elif action.kind == "protection":
            ensure_branch_protection(client, config)

    return actions


def ensure_branch_protection(client, config: GovernanceConfig) -> dict:
    """PUT the protection payload, refusing to run against a missing branch."""
    branch = config.branch_protection.branch
    try:
        client.get(f"{repo_path(config)}/branches/{branch}")
    except NotFoundError as exc:
        raise BranchMissingError(
            f"branch '{branch}' does not exist yet — push at least one commit "
            "before protecting it"
        ) from exc
    return client.put(
        f"{repo_path(config)}/branches/{branch}/protection",
        build_protection_payload(config.branch_protection),
    )
