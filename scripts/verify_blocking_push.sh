#!/usr/bin/env bash
# AC-3 negative proof: a REAL push to `main` must be rejected by branch protection.
#
# Safety design:
#   - the probe is an EMPTY commit, it carries no data
#   - if the push unexpectedly succeeds (protection missing!), we force-push
#     `main` back to its previous SHA immediately and exit 1 — self-healing
#   - refuses to run on a dirty tree or with unpushed local commits
set -euo pipefail

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "REFUSING: working tree is not clean — commit or stash first." >&2
  exit 1
fi

BEFORE="$(git ls-remote origin refs/heads/main | cut -f1)"
if [ -z "$BEFORE" ]; then
  echo "REFUSING: origin/main has no commits; nothing to protect yet." >&2
  exit 1
fi

LOCAL_MAIN="$(git rev-parse main)"
if [ "$LOCAL_MAIN" != "$BEFORE" ]; then
  echo "REFUSING: local main ($LOCAL_MAIN) != origin/main ($BEFORE). Push or pull first." >&2
  exit 1
fi

cleanup() { git checkout main --quiet 2>/dev/null || true; }
trap cleanup EXIT

git fetch origin main --quiet
git checkout --detach origin/main --quiet
git commit --allow-empty --quiet -m "probe: direct push to main must be rejected (AC-3)"

echo "-- attempting direct push to main (this SHOULD fail) --"
if OUT="$(git push origin HEAD:main 2>&1)"; then
  echo "FAIL: direct push to main SUCCEEDED — branch protection is NOT enforced." >&2
  echo "-- rolling back main to $BEFORE --"
  if git push --force origin "$BEFORE:refs/heads/main" >/dev/null 2>&1; then
    echo "rollback complete: main restored to $BEFORE"
  else
    echo "MANUAL ACTION REQUIRED: git push --force origin $BEFORE:main" >&2
  fi
  exit 1
fi

echo "$OUT"
if ! echo "$OUT" | grep -qiE "protected branch|GH006|remote rejected|protected branch hook"; then
  echo "AMBIGUOUS: push failed, but NOT with a protection error — investigate above." >&2
  exit 1
fi

echo "PASS (AC-3): direct push to main was rejected by branch protection."
