# Ticket 001 — Protected `main` branch

**Status:** enforcement moved to the `main` ruleset + branch protection — governance-as-code removed 2026-11-04 · **Owner:** ismail-ougamane · **Date:** 2026-11-02 (created)

> As a team member, I want `main` to be protected so that every change is
> reviewed before it lands.

## Acceptance criteria (verified against the live GitHub API — no test code lives in the repo)

| ID | Criterion | How to re-verify (read-only) |
|----|-----------|------------------------------|
| AC-1 | Repository created, public, `main` is the default branch with history | `gh api repos/ismail-ougamane/GitHub_Analytics_Data_Engineering_Flow --jq '{private,visibility,default_branch}'` → `{private:false, visibility:"public", default_branch:"main"}` |
| AC-1b | Every colleague has write access | `gh api repos/…/collaborators --jq '.[] \| {login, role_name}'` → every non-owner has `write` or better |
| AC-2 | `main` requires a PR with ≥ 1 approval | `gh api repos/…/branches/main/protection` → `required_pull_request_reviews.required_approving_review_count >= 1` |
| AC-3 | Direct pushes to `main` are blocked | same endpoint → `enforce_admins.enabled == true`, `allow_force_pushes.enabled == false`, `allow_deletions.enabled == false`; the ruleset additionally blocks deletion and non-fast-forward |
| AC-4 | ~~Governance is idempotent, no drift~~ | **Retired 2026-11-04** together with the `plan`/`apply` tooling — enforcement moved to the ruleset + branch protection |

## Plan (decisions D1–D10)

- **D1** `visibility: public` — GitHub Free cannot protect private branches
  ([docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)).
- **D2** Classic branch protection (not rulesets) — maps 1:1 to the AC wording.
- **D3** `enforce_admins: true` — otherwise the owner bypasses AC-3.
- **D4** `required_approving_review_count: 1`, `dismiss_stale_reviews`,
  `require_last_push_approval`, `required_conversation_resolution`.
- **D5** `allow_force_pushes: false`, `allow_deletions: false`,
  `required_linear_history: true`.
- **D6** Collaborators get `push`; an empty collaborator list must never pass AC-1b.
- **D7** No break-glass path: a merge requires a real second human (GitHub
  forbids self-approval).
- **D8** Two test layers: offline `tests/unit` (every PR) and `tests/live`
  (`GOVERNANCE_LIVE=1`).
- **D9** `require_code_owner_reviews: false` until ≥ 2 humans exist.
- **D10** Secret gate before any push: `make secret-scan` + GitHub
  secret-scanning push protection.

## TDD log

- [x] **RED (offline)** — `26 collected` but `src/` absent:
  `6 passed, 3 errors` (3× `ModuleNotFoundError: No module named 'github_governance'`)
- [x] **GREEN (offline)** — implementation written; found 2 real bugs via tests
  (fake path-parsing `parts[2:]` vs `parts[3:]`, fake PUT-protection 404 on
  creation); final: `26 passed, 0 failed`, `ruff check`: clean
- [x] **RED (live)** — `5 failed, 2 passed, 2 skipped`:
  AC-1 passed; AC-2/AC-3/AC-4 failed (`Branches::get` protection → 404,
  "Branch not protected"); AC-1b skipped loudly (no collaborators configured)
- [x] **GREEN (live)** — after `make apply`:
  `7 passed, 2 skipped` (only AC-1b skips, pending teammate usernames)
- [x] **AC-3 negative proof** — `make verify-blocking-push`:

  ```
  remote: error: GH006: Protected branch update failed for refs/heads/main.
  remote: - Changes must be made through a pull request.
  ! [remote rejected] HEAD -> main (protected branch hook declined)
  PASS (AC-3): direct push to main was rejected by branch protection.
  ```

  Note: the rejected push came from the repository **owner** —
  `enforce_admins` is doing its job.

## Verification matrix (final state, 2026-11-02)

| ID | Criterion | Result | Evidence |
|----|-----------|--------|----------|
| AC-1 | Repo created, public, `main` default with history | ✅ pass | `test_ac1_repository.py` (live, green) |
| AC-1b | Every colleague has write access | ⏸️ skipped | `test_ac1b_collaborators.py` — loud skip: no collaborators configured yet |
| AC-2 | PR required with ≥ 1 approval | ✅ pass | `test_ac2_reviews.py` (live, green) |
| AC-3 | Direct pushes blocked | ✅ pass | `test_ac3_no_direct_push.py` + real `GH006` rejection above |
| AC-4 | Idempotent, no drift | ✅ pass | `make plan` after apply → "No drift"; `test_ac4_idempotent_apply.py` green |

Idempotency also proven at the CLI level: the second `apply_governance.py
--plan` printed `No drift: repository matches the desired state.`

## Live re-validation — 2026-11-04 (GitHub Actions removed)

The `governance` workflow was removed (see changelog). Every acceptance
criterion was re-validated directly against the live GitHub API (`gh api`,
read-only) instead of CI:

| ID | Criterion | Result | Live evidence (2026-11-04) |
|----|-----------|--------|----------------------------|
| AC-1 | Repo created, public, `main` default with history | ✅ pass | `gh api repos/…`: `private:false`, `visibility:public`, `default_branch:main`; 2 commits on `main` |
| AC-1b | Every colleague has write access | ✅ pass (fact) · ⏸️ test still skips | collaborators: `mektoubizakaria` → `role_name:"write"`, `othmane-fathallah` → `role_name:"write"`; owner → `admin`. `config/governance.toml` still lists 0 collaborators, so `test_ac1b_collaborators.py` keeps its loud skip (D6) |
| AC-2 | PR required with ≥ 1 approval | ✅ pass | `required_approving_review_count:1`, `dismiss_stale_reviews:true`, `require_last_push_approval:true` |
| AC-3 | Direct pushes blocked | ✅ pass | `enforce_admins:{enabled:true}`, `allow_force_pushes:{enabled:false}`, `allow_deletions:{enabled:false}`, `required_pull_request_reviews` present |
| AC-4 | Idempotent, no drift | ✅ pass | `apply_governance.py --plan` → `No drift: repository matches the desired state.` |

Offline suites at validation time: `tests/unit` 26 passed · `tests/live`
7 passed, 2 skipped (AC-1b) · `ruff check` clean.

Findings recorded on 2026-11-04:

- **Ruleset `main` (id 26561116) is `enforcement: disabled`.** It was added in
  the GitHub UI on 2026-11-04 but currently enforces nothing; classic branch
  protection is what makes AC-2/AC-3 pass. If it is meant to replace the
  workflow it must be activated — and it would still not cover
  `required_linear_history` / `required_conversation_resolution`.
- **PR #2 was approved by `othmane-fathallah` and then closed unmerged** — the
  first real review exercised by the protected flow, but its ticket evidence
  only landed with the PR that removed Actions.
- The workflow version on `main` could never pass (invalid `administration`
  scope — every `push` run failed in ~0s), so removing it fixes red CI rather
  than losing a working check.

## Governance-as-code removed — 2026-11-04

With the ruleset intended as the enforcement layer, the executable governance
machinery was deleted in full: `src/github_governance/`,
`scripts/apply_governance.py`, `scripts/verify_blocking_push.sh`, `tests/`
(unit + live), `config/governance.toml`, `Makefile` and `pyproject.toml`.
The repository keeps only docs, tickets and GitHub settings.

What enforces the criteria now (observed state, 2026-11-04):

- **Ruleset `main` (26561116)**: `pull_request` (1 approval, stale-review
  dismissal, last-push approval), plus `deletion` and `non_fast_forward`
  blocked. ⚠️ Observed `enforcement: disabled` via the API at removal time —
  activate it in Settings → Rules → Rulesets, or with
  `gh api -X PUT repos/ismail-ougamane/GitHub_Analytics_Data_Engineering_Flow/rulesets/26561116 -f enforcement=active`.
  Until then **classic branch protection is the enforcing layer**.
- **Classic branch protection on `main`** (still active): 1 approval,
  stale-review dismissal, last-push approval, `enforce_admins`, linear
  history, conversation resolution, no force-push/deletion.
- **GitHub secret scanning + push protection** (the secret gate).

AC-1 … AC-3 and AC-1b were re-verified live on 2026-11-04 (re-validation
table above); AC-4 is retired with the tooling.

## Changelog

### 2026-11-04 — governance-as-code removed
- **Removed all governance code**: `src/github_governance/`,
  `scripts/apply_governance.py`, `scripts/verify_blocking_push.sh`, `tests/`
  (unit + live), `config/governance.toml`, `Makefile`, `pyproject.toml` — the
  ruleset + branch protection carry enforcement, so the executable layer is
  no longer wanted in the repo.
- Rewrote `README.md`, `CONTRIBUTING.md` and the PR template; trimmed
  `.gitignore`; updated the ticket index status.
- AC-4 retired; AC-1 … AC-3 + AC-1b re-verified live with `gh api`.
- Caveat recorded: ruleset `main` observed `enforcement: disabled` at removal
  time; classic branch protection active and enforcing.

### 2026-11-04
- **Removed GitHub Actions** (`.github/workflows/governance.yml`). Rationale:
  the version on `main` carried the invalid `administration: read`
  GITHUB_TOKEN scope and could never run (all three `push` runs failed in
  ~0s); enforcement of the ACs lives in GitHub branch protection plus the
  repository ruleset; verification remains available locally via `make test`
  and `make test-live`.
- Re-validated every AC live with `gh api` (table above) — all pass. AC-1b
  still skips in tests until collaborators are added to
  `config/governance.toml`; two colleagues already have write access live.
- Recorded that the ruleset `main` (26561116) is disabled, and that PR #2
  (approved by `othmane-fathallah`) was closed unmerged.
- Fixed `README.md` linking to the non-existent `config/governance.yaml` →
  `config/governance.toml`.

### 2026-11-02
- Created repository `GitHub_Analytics_Data_Engineering_Flow` (public, GitHub
  Free) and enabled secret scanning + push protection.
- Bootstrap commit `176652d` on `main` (README/LICENSE/.gitignore/pyproject) —
  the only direct push to `main`, required because a base branch must exist
  before a PR can.
- Scaffolded governance-as-code (config, client, converge, tests) and shipped
  it via PR #1 (squash-merged as `9f5f604`) — bootstrap exception #2, merged
  before protection could exist.
- Applied branch protection on `main` with `make apply`
  (`PUT /branches/main/protection`): 1 required approval, stale-review
  dismissal, last-push approval, admin enforcement, no force-push/deletion,
  linear history, conversation resolution.
- Verified all live ACs green (`7 passed, 2 skipped`) and proved AC-3 with a
  real `GH006` rejection of a direct push by the owner.
- **Incident (CI):** all three initial `push` runs failed with *"This run
  likely failed because of a workflow file issue"* — root cause:
  `permissions: administration: read` is not a valid GITHUB_TOKEN permission
  scope, so GitHub rejected the workflow at validation time (zero jobs
  executed; the failure was in the file, not the code). Fix: dropped the
  invalid scope and moved the weekly drift check to a `GOVERNANCE_TOKEN` PAT
  secret with a graceful skip when the secret is absent — GITHUB_TOKEN can
  never read branch protection.

