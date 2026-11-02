"""Unit tests for the desired-state spec loader (config/governance.toml).

The spec loader is the policy gate: it must REFUSE configs that would silently
weaken the acceptance criteria (Ticket 001):
  - AC-2 requires >= 1 approving review -> a spec with 0 is a bug, not a setting
  - AC-3 requires direct pushes blocked for EVERYONE -> enforce_admins must be true
  - history safety: force pushes / deletions must stay disabled
  - GitHub Free cannot protect private branches -> visibility=private needs
    an explicit allow_private escape hatch (and a plan that supports it)
"""
from __future__ import annotations

import pytest

from github_governance.errors import ConfigError
from github_governance.settings import BranchProtectionSpec, RepositorySpec, load_config


def _protection_dict(**overrides) -> dict:
    base = {
        "branch": "main",
        "required_approving_review_count": 1,
        "dismiss_stale_reviews": True,
        "require_code_owner_reviews": False,
        "require_last_push_approval": True,
        "enforce_admins": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "required_linear_history": True,
        "required_conversation_resolution": True,
    }
    base.update(overrides)
    return base


class TestLoadConfig:
    def test_loads_the_repository_governance_config(self, config):
        assert config.repository.owner == "ismail-ougamane"
        assert config.repository.name == "GitHub_Analytics_Data_Engineering_Flow"
        assert config.repository.visibility == "public"
        assert config.branch_protection.branch == "main"

    def test_unknown_top_level_key_is_rejected(self, tmp_path):
        path = tmp_path / "governance.toml"
        path.write_text(
            '[repository]\nowner = "o"\nname = "r"\n\n[bogus_section]\nkey = "x"\n'
        )
        with pytest.raises(ConfigError, match="unknown"):
            load_config(path)


class TestRepositorySpec:
    def test_private_visibility_without_escape_hatch_is_rejected(self):
        with pytest.raises(ConfigError, match="GitHub Free"):
            RepositorySpec.from_dict(
                {
                    "owner": "ismail-ougamane",
                    "name": "GitHub_Analytics_Data_Engineering_Flow",
                    "visibility": "private",
                    "allow_private": False,
                }
            )

    def test_private_visibility_with_explicit_escape_hatch_is_allowed(self):
        spec = RepositorySpec.from_dict(
            {
                "owner": "ismail-ougamane",
                "name": "GitHub_Analytics_Data_Engineering_Flow",
                "visibility": "private",
                "allow_private": True,
            }
        )
        assert spec.visibility == "private"

    def test_unknown_visibility_is_rejected(self):
        with pytest.raises(ConfigError, match="visibility"):
            RepositorySpec.from_dict(
                {
                    "owner": "o",
                    "name": "r",
                    "visibility": "internal",
                    "allow_private": False,
                }
            )


class TestBranchProtectionSpec:
    def test_zero_required_approvals_is_rejected(self):
        with pytest.raises(ConfigError, match="AC-2"):
            BranchProtectionSpec.from_dict(_protection_dict(required_approving_review_count=0))

    def test_admin_bypass_is_rejected(self):
        with pytest.raises(ConfigError, match="AC-3"):
            BranchProtectionSpec.from_dict(_protection_dict(enforce_admins=False))

    def test_force_pushes_must_stay_disabled(self):
        with pytest.raises(ConfigError, match="force push"):
            BranchProtectionSpec.from_dict(_protection_dict(allow_force_pushes=True))

    def test_branch_deletion_must_stay_disabled(self):
        with pytest.raises(ConfigError, match="delet"):
            BranchProtectionSpec.from_dict(_protection_dict(allow_deletions=True))

    def test_unknown_branch_is_rejected(self):
        with pytest.raises(ConfigError, match="branch"):
            BranchProtectionSpec.from_dict(_protection_dict(branch="master"))
