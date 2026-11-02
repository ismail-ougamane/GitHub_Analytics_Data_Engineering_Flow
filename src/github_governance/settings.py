"""Desired-state spec loaded from config/governance.toml.

The loader is the policy gate: configs that would weaken the acceptance
criteria are rejected at load time, never silently applied.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from github_governance.errors import ConfigError

_DOCS_URL = (
    "https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/"
    "managing-protected-branches/about-protected-branches"
)

_TOP_LEVEL_KEYS = {"repository", "branch_protection", "collaborators"}


@dataclass(frozen=True)
class RepositorySpec:
    owner: str
    name: str
    visibility: str
    allow_private: bool
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> RepositorySpec:
        visibility = data.get("visibility", "public")
        if visibility not in ("public", "private"):
            raise ConfigError(
                f"repository.visibility must be 'public' or 'private', got {visibility!r}"
            )
        if visibility == "private" and not data.get("allow_private", False):
            raise ConfigError(
                "repository.visibility='private' is rejected: GitHub Free cannot protect "
                f"private branches, so AC-2/AC-3 would be unenforceable. See {_DOCS_URL}. "
                "Set allow_private = true ONLY after upgrading the account plan."
            )
        return cls(
            owner=data["owner"],
            name=data["name"],
            visibility=visibility,
            allow_private=bool(data.get("allow_private", False)),
            description=data.get("description", ""),
        )


@dataclass(frozen=True)
class CollaboratorSpec:
    login: str
    permission: str = "push"

    @classmethod
    def from_dict(cls, data: dict) -> CollaboratorSpec:
        login = data.get("login", "").strip()
        if not login:
            raise ConfigError("collaborators entry missing 'login'")
        permission = data.get("permission", "push")
        if permission not in ("push", "maintain", "admin"):
            raise ConfigError(
                f"collaborator permission must be push|maintain|admin, got {permission!r}"
            )
        return cls(login=login, permission=permission)


_PROTECTION_KEYS = {
    "branch",
    "required_approving_review_count",
    "dismiss_stale_reviews",
    "require_code_owner_reviews",
    "require_last_push_approval",
    "enforce_admins",
    "allow_force_pushes",
    "allow_deletions",
    "required_linear_history",
    "required_conversation_resolution",
}


@dataclass(frozen=True)
class BranchProtectionSpec:
    branch: str
    required_approving_review_count: int
    dismiss_stale_reviews: bool
    require_code_owner_reviews: bool
    require_last_push_approval: bool
    enforce_admins: bool
    allow_force_pushes: bool
    allow_deletions: bool
    required_linear_history: bool
    required_conversation_resolution: bool

    @classmethod
    def from_dict(cls, data: dict) -> BranchProtectionSpec:
        unknown = set(data) - _PROTECTION_KEYS
        if unknown:
            raise ConfigError(f"unknown branch_protection key(s): {sorted(unknown)}")

        branch = data.get("branch", "")
        if branch != "main":
            raise ConfigError(
                f"branch_protection.branch must be 'main' (this governance protects main), "
                f"got {branch!r}"
            )

        count = data.get("required_approving_review_count")
        if not isinstance(count, int) or count < 1:
            raise ConfigError(
                "AC-2 requires required_approving_review_count >= 1; 0 would silently "
                "weaken the review gate"
            )

        if not data.get("enforce_admins", False):
            raise ConfigError(
                "AC-3 requires enforce_admins = true: without it repository admins can "
                "push directly to main and bypass the review requirement"
            )

        if data.get("allow_force_pushes", False):
            raise ConfigError(
                "allow_force_pushes must stay disabled: a force push would rewrite "
                "reviewed history"
            )

        if data.get("allow_deletions", False):
            raise ConfigError(
                "allow_deletions must stay disabled: main must not be deletable"
            )

        return cls(
            branch=branch,
            required_approving_review_count=count,
            dismiss_stale_reviews=bool(data.get("dismiss_stale_reviews", True)),
            require_code_owner_reviews=bool(data.get("require_code_owner_reviews", False)),
            require_last_push_approval=bool(data.get("require_last_push_approval", True)),
            enforce_admins=True,
            allow_force_pushes=False,
            allow_deletions=False,
            required_linear_history=bool(data.get("required_linear_history", True)),
            required_conversation_resolution=bool(
                data.get("required_conversation_resolution", True)
            ),
        )


@dataclass(frozen=True)
class GovernanceConfig:
    repository: RepositorySpec
    branch_protection: BranchProtectionSpec
    collaborators: tuple[CollaboratorSpec, ...] = field(default=())


def load_config(path: Path) -> GovernanceConfig:
    with open(path, "rb") as handle:
        raw = tomllib.load(handle)

    unknown = set(raw) - _TOP_LEVEL_KEYS
    if unknown:
        raise ConfigError(f"unknown top-level key(s) in config: {sorted(unknown)}")

    if "repository" not in raw or "branch_protection" not in raw:
        raise ConfigError("config must define [repository] and [branch_protection]")

    collaborators = tuple(
        CollaboratorSpec.from_dict(entry) for entry in raw.get("collaborators", [])
    )
    return GovernanceConfig(
        repository=RepositorySpec.from_dict(raw["repository"]),
        branch_protection=BranchProtectionSpec.from_dict(raw["branch_protection"]),
        collaborators=collaborators,
    )
