"""Thin GitHub REST client with typed errors.

Only what the governance flow needs — no SDK dependency. Token comes from the
environment: GOVERNANCE_TOKEN, GH_TOKEN (e.g. `export GH_TOKEN=$(gh auth token)`)
or GITHUB_TOKEN.
"""
from __future__ import annotations

import os
import re

import requests

from github_governance.errors import AuthError, GitHubError, NotFoundError, PermissionDeniedError

API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
_TIMEOUT_SECONDS = 30

_PLAN_GATED_HINT = re.compile(
    r"upgrade to github pro|make this repository public", re.IGNORECASE
)


class GitHubClient:
    def __init__(
        self,
        token: str,
        base_url: str = API_ROOT,
        session: requests.Session | None = None,
    ):
        if not token:
            raise AuthError("empty GitHub token")
        self._base = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": _API_VERSION,
            }
        )

    @classmethod
    def from_env(cls) -> GitHubClient:
        token = (
            os.environ.get("GOVERNANCE_TOKEN")
            or os.environ.get("GH_TOKEN")
            or os.environ.get("GITHUB_TOKEN")
        )
        if not token:
            raise AuthError(
                "no GitHub token in environment; run `export GH_TOKEN=$(gh auth token)`"
            )
        return cls(token)

    # -- public surface (mirrored by tests/conftest.py::FakeClient) ----------
    def get(self, path: str) -> dict:
        return self._request("GET", path)

    def put(self, path: str, json: dict | None = None) -> dict:
        return self._request("PUT", path, json)

    def patch(self, path: str, json: dict | None = None) -> dict:
        return self._request("PATCH", path, json)

    # -- internals ------------------------------------------------------------
    def _request(self, method: str, path: str, json: dict | None = None) -> dict:
        response = self._session.request(
            method, f"{self._base}{path}", json=json, timeout=_TIMEOUT_SECONDS
        )
        if response.status_code < 300:
            return response.json() if response.content else {}
        message = _error_message(response)
        if response.status_code == 404:
            raise NotFoundError(f"404 {path}: {message}")
        if response.status_code in (401, 403):
            kind = "plan_gated" if _PLAN_GATED_HINT.search(message) else "generic"
            raise PermissionDeniedError(
                f"{response.status_code} {path}: {message}", kind=kind
            )
        raise GitHubError(f"{response.status_code} {path}: {message}")


def _error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(payload, dict):
        return str(payload.get("message", payload))
    return str(payload)
