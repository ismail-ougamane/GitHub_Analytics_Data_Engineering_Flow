"""Typed errors shared by the client, settings loader, and converge flow."""


class GitHubError(Exception):
    """Any non-success response from the GitHub API."""


class NotFoundError(GitHubError):
    """404 — resource does not exist (repo, branch, protection...)."""


class PermissionDeniedError(GitHubError):
    """401/403 — bad token, missing scope, or plan-gated feature."""

    def __init__(self, message: str, kind: str = "generic"):
        super().__init__(message)
        # kind == "plan_gated": GitHub Free trying to protect a private branch
        self.kind = kind


class AuthError(GitHubError):
    """No usable credentials configured."""


class ConfigError(Exception):
    """config/governance.toml violates the governance policy."""


class BranchMissingError(Exception):
    """Tried to protect a branch that has no commits yet."""
