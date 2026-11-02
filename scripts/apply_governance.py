#!/usr/bin/env python3
"""Plan or apply the governance desired state against the live repository.

    python scripts/apply_governance.py --plan   # drift report, read-only
    python scripts/apply_governance.py --apply  # converge (idempotent)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from github_governance.client import GitHubClient  # noqa: E402
from github_governance.converge import apply_governance, plan_changes  # noqa: E402
from github_governance.errors import GitHubError  # noqa: E402
from github_governance.settings import load_config  # noqa: E402

DEFAULT_CONFIG = REPO_ROOT / "config" / "governance.toml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan", action="store_true", help="drift report (read-only)")
    group.add_argument("--apply", action="store_true", help="converge to desired state")
    args = parser.parse_args()

    config = load_config(args.config)
    client = GitHubClient.from_env()

    try:
        if args.plan:
            actions = plan_changes(client, config)
            if not actions:
                print("No drift: repository matches the desired state.")
            else:
                print(f"Drift detected — {len(actions)} action(s) needed:")
                for action in actions:
                    print(f"  {action!r}")
            return 0

        applied = apply_governance(client, config)
        if not applied:
            print("Nothing to do: repository already converged.")
        else:
            print(f"Applied {len(applied)} change(s):")
            for action in applied:
                print(f"  {action!r}")
        return 0
    except GitHubError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
