"""Shared fixtures: config loading, an offline GitHub API double, and the live client.

Test layers (Ticket 001, decision D8):
  - tests/unit : offline, fast, must pass on every PR (no network, FakeClient)
  - tests/live : assert the REAL repo state; deselected unless GOVERNANCE_LIVE=1
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "governance.toml"


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live: asserts real GitHub state (needs GOVERNANCE_LIVE=1)"
    )


def pytest_collection_modifyitems(config, items):
    if os.environ.get("GOVERNANCE_LIVE") == "1":
        return
    skip = pytest.mark.skip(reason="live test: set GOVERNANCE_LIVE=1 to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def config():
    from github_governance.settings import load_config

    return load_config(CONFIG_PATH)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self) -> dict:
        return self._payload


class FakeClient:
    """Offline double of github_governance.client.GitHubClient.

    Same public surface (get/put/patch + typed errors) so the converge code is
    tested against the exact contract it will meet on the real API. Records
    every call so tests can assert on side effects (idempotency, ordering).
    """

    def __init__(self, state: dict | None = None):
        self.calls: list[tuple[str, str, dict | None]] = []
        self.state = state or {
            "repo": {
                "full_name": "ismail-ougamane/GitHub_Analytics_Data_Engineering_Flow",
                "private": True,
                "default_branch": "main",
                "visibility": "private",
            },
            "repo_missing": False,
            "branch_exists": False,
            "collaborators": [],
            "invitations": [],
            "protection": None,
        }

    # -- endpoint dispatch ---------------------------------------------------
    def request(self, method: str, path: str, json: dict | None = None) -> FakeResponse:
        self.calls.append((method, path, json))
        parts = [p for p in path.split("/") if p]
        assert parts[0] == "repos", f"FakeClient: unexpected path {path}"
        rest = parts[3:]  # strip /repos/{owner}/{repo}

        if not rest:
            if self.state["repo_missing"]:
                return FakeResponse(404, {"message": "Not Found"})
            if method == "GET":
                return FakeResponse(200, dict(self.state["repo"]))
            if method == "PATCH":
                self.state["repo"].update(json or {})
                self.state["visibility_changes"] = (
                    self.state.get("visibility_changes", 0) + 1
                )
                return FakeResponse(200, dict(self.state["repo"]))

        if rest == ["collaborators"] and method == "GET":
            return FakeResponse(200, list(self.state["collaborators"]))

        if rest == ["invitations"] and method == "GET":
            return FakeResponse(200, [{"login": login} for login in self.state["invitations"]])

        if len(rest) == 2 and rest[0] == "collaborators" and method == "PUT":
            login = rest[1]
            if any(c["login"] == login for c in self.state["collaborators"]):
                return FakeResponse(204, {})
            if login not in self.state["invitations"]:
                self.state["invitations"].append(login)
            return FakeResponse(201, {"login": login})

        if rest == ["branches", "main"] and method == "GET":
            if self.state["branch_exists"]:
                return FakeResponse(200, {"name": "main"})
            return FakeResponse(404, {"message": "Not Found"})

        if rest == ["branches", "main", "protection"]:
            if method == "GET":
                if not self.state["branch_exists"] or self.state["protection"] is None:
                    return FakeResponse(404, {"message": "Not Found"})
                return FakeResponse(200, self._api_shape(self.state["protection"]))
            if method == "PUT":
                if not self.state["branch_exists"]:
                    return FakeResponse(404, {"message": "Branch not found"})
                self.state["protection"] = json
                return FakeResponse(200, {})

        raise AssertionError(f"FakeClient: unhandled {method} {path}")

    @staticmethod
    def _api_shape(payload: dict) -> dict:
        """Re-shape a PUT payload the way GitHub's GET endpoint returns it."""
        return {
            "enforce_admins": {"enabled": payload["enforce_admins"]},
            "required_pull_request_reviews": payload["required_pull_request_reviews"],
            "required_status_checks": payload.get("required_status_checks"),
            "restrictions": payload.get("restrictions"),
            "allow_force_pushes": {"enabled": payload["allow_force_pushes"]},
            "allow_deletions": {"enabled": payload["allow_deletions"]},
            "required_linear_history": {"enabled": payload["required_linear_history"]},
            "required_conversation_resolution": {
                "enabled": payload["required_conversation_resolution"]
            },
        }

    # -- GitHubClient-compatible surface ------------------------------------
    def _raise_for_status(self, response: FakeResponse) -> None:
        from github_governance.errors import NotFoundError

        if response.status_code == 404:
            raise NotFoundError(f"404: {response.json().get('message', 'Not Found')}")

    def get(self, path: str) -> dict:
        response = self.request("GET", path)
        self._raise_for_status(response)
        return response.json()

    def put(self, path: str, json: dict | None = None) -> dict:
        response = self.request("PUT", path, json)
        self._raise_for_status(response)
        return response.json()

    def patch(self, path: str, json: dict | None = None) -> dict:
        response = self.request("PATCH", path, json)
        self._raise_for_status(response)
        return response.json()


@pytest.fixture
def fake_client():
    return FakeClient()


@pytest.fixture(scope="session")
def live_client():
    from github_governance.client import GitHubClient

    return GitHubClient.from_env()
