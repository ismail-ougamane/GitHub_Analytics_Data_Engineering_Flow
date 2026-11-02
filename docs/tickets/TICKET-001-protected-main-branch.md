# Ticket 001 — Protected `main` branch

**Status:** protection applied — awaiting first reviewed PR (#2) to close · **Owner:** ismail-ougamane · **Date:** 2026-11-02

> As a team member, I want `main` to be protected so that every change is
> reviewed before it lands.

## Acceptance criteria (each one is a live test, see `tests/live/`)

| ID | Criterion | Proof |
|----|-----------|-------|
| AC-1 | Repository created, public, `main` is the default branch with history | `tests/live/test_ac1_repository.py` |
| AC-1b | Every colleague has write access | `tests/live/test_ac1b_collaborators.py` (loud `SKIPPED` until collaborators are configured) |
| AC-2 | `main` requires a PR with ≥ 1 approval | `tests/live/test_ac2_reviews.py` |
| AC-3 | Direct pushes to `main` are blocked | `tests/live/test_ac3_no_direct_push.py` + `make verify-blocking-push` |
| AC-4 | Governance is idempotent, no drift | `tests/live/test_ac4_idempotent_apply.py` |

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

## Changelog

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

