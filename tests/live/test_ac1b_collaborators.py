"""AC-1b: every configured colleague has write access.

Deliberate honesty rule (decision D6): an EMPTY collaborator list must never
look like success — it skips loudly instead. Add usernames to
config/governance.toml -> [[collaborators]] to activate.
"""
from __future__ import annotations

import pytest


@pytest.mark.live
def test_every_configured_colleague_has_write_access(live_client, config):
    if not config.collaborators:
        pytest.skip(
            "AC-1b incomplete: no collaborators configured in config/governance.toml "
            "(add [[collaborators]] entries with login + permission = 'push')"
        )

    owner, name = config.repository.owner, config.repository.name
    collaborators = live_client.get(f"/repos/{owner}/{name}/collaborators")
    permissions = {c["login"]: c.get("permissions", {}) for c in collaborators}
    invitations = live_client.get(f"/repos/{owner}/{name}/invitations")
    pending = {i["login"] for i in invitations}

    failures = []
    for collab in config.collaborators:
        login = collab.login
        perms = permissions.get(login)
        has_write = bool(perms and (perms.get("push") or perms.get("admin")))
        if not has_write and login not in pending:
            failures.append(
                f"{login}: no write access and no pending invitation "
                f"(known collaborators: {sorted(permissions)})"
            )
    assert failures == [], "colleagues without write access:\n" + "\n".join(failures)


@pytest.mark.live
def test_collaborators_get_at_least_push(live_client, config):
    """Write access means `push` or better — read-only is not enough (AC-1)."""
    if not config.collaborators:
        pytest.skip("AC-1b incomplete: no collaborators configured")

    collaborators = live_client.get(
        f"/repos/{config.repository.owner}/{config.repository.name}/collaborators"
    )
    by_login = {c["login"]: c for c in collaborators}
    for collab in config.collaborators:
        entry = by_login.get(collab.login)
        assert entry is not None, f"{collab.login} is not a collaborator yet"
        role = entry.get("role_name", "")
        assert role in ("write", "admin", "maintain"), (
            f"{collab.login} has role '{role}', expected at least 'write' (push)"
        )
