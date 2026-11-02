# Ticket 001 — Protected `main` branch

**Status:** in progress · **Owner:** ismail-ougamane · **Date:** 2026-11-02

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

- [ ] RED (offline) — unit tests fail because `src/` does not exist yet
- [ ] GREEN (offline) — implementation makes unit tests pass
- [ ] RED (live) — AC tests fail: no protection on `main`
- [ ] GREEN (live) — `make apply` converges the repo; live tests pass
- [ ] AC-3 negative proof — `make verify-blocking-push` rejects a real push

## Changelog

### 2026-11-02
- Created repository `GitHub_Analytics_Data_Engineering_Flow` (public, GitHub
  Free) and enabled secret scanning + push protection.
- Bootstrap commit `176652d` on `main` (README/LICENSE/.gitignore/pyproject) —
  the only direct push to `main`, required because a base branch must exist
  before a PR can.
- Scaffolded governance-as-code (config, client, converge, tests) on branch
  `chore/ticket-001-governance-scaffold`, shipped via pull request.
