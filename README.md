# GitHub Analytics Data Engineering Flow

End-to-end data engineering project: ingestion, modeling, and analytics over
GitHub activity data.

## How we work

- `main` is protected: changes land via pull request with **≥ 1 approval**,
  enforced by a GitHub
  [ruleset](https://github.com/ismail-ougamane/GitHub_Analytics_Data_Engineering_Flow/rules/26561116)
  plus classic branch protection — no custom code needed.
- Every ticket ships a `docs/tickets/TICKET-XXX-*.md` file containing its
  **plan** and a dated **changelog**.
- No secrets, ever: GitHub secret scanning and push protection are active.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the review workflow, and
[docs/tickets/README.md](docs/tickets/README.md) for the ticket index.

## Branching & pull request workflow

**One phase = one feature branch = one pull request.** Each ticket gets its own
branch off `main` — `feat/ticket-XXX-slug` (or `fix`/`chore`/`docs`/`test`) —
and exactly one pull request.

**Pull requests start as drafts.** Open with `gh pr create --fill --draft`, flip
to ready with `gh pr ready`, and merge only after review (≥ 1 approval, enforced
by the ruleset). Squash-merge, then delete the branch.

**The 7-step loop:**

1. **Goal** — pick the ticket, write its acceptance criteria.
2. **Branch** — `git checkout -b feat/ticket-XXX-slug`
3. **Build** — smallest change that meets the criteria.
4. **Test** — prove the criteria, record the result.
5. **Document** — add a changelog entry to the ticket doc.
6. **PR** — open a draft PR, then mark it ready.
7. **Share** — request review, get 1 approval, squash-merge, delete branch.
