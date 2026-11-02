"""The exact JSON body sent to PUT /repos/{owner}/{repo}/branches/{branch}/protection.

This payload IS the acceptance criteria, encoded. If someone changes it, these
tests fail — which is the point.
"""
from __future__ import annotations

from github_governance.branch_protection import build_protection_payload


class TestProtectionPayload:
    def test_payload_encodes_all_four_acceptance_criteria(self, config):
        payload = build_protection_payload(config.branch_protection)

        # AC-2: PR required with >= 1 approval, stale reviews dismissed,
        #       and a push after the last approval invalidates it
        reviews = payload["required_pull_request_reviews"]
        assert reviews["required_approving_review_count"] >= 1
        assert reviews["dismiss_stale_reviews"] is True
        assert reviews["require_last_push_approval"] is True

        # AC-3: direct pushes blocked for everyone, admins included
        assert payload["enforce_admins"] is True

        # D5: history safety
        assert payload["allow_force_pushes"] is False
        assert payload["allow_deletions"] is False

    def test_payload_contains_exactly_the_fields_the_endpoint_accepts(self, config):
        payload = build_protection_payload(config.branch_protection)
        assert set(payload) == {
            "required_status_checks",
            "enforce_admins",
            "required_pull_request_reviews",
            "restrictions",
            "required_linear_history",
            "allow_force_pushes",
            "allow_deletions",
            "required_conversation_resolution",
        }

    def test_no_status_checks_required_yet(self, config):
        # CI does not gate merges yet (Ticket 001 scope); explicitly null,
        # never accidentally omitted-and-ignored.
        payload = build_protection_payload(config.branch_protection)
        assert payload["required_status_checks"] is None
        assert payload["restrictions"] is None
