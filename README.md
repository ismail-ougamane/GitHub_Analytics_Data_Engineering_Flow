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

## Run Airflow locally

The orchestration layer lives in [`orchestration/`](orchestration/) as an
[Astro](https://www.astronomer.io/docs/astro/cli/overview) project — Astro
Runtime 3.3-12, i.e. Apache Airflow 3.3 (Python 3.14) in Docker.

**One-time setup** (see the [Astro install docs](https://www.astronomer.io/docs/astro/cli/install-cli)):

```bash
brew tap astronomer/tap && brew install astronomer/tap/astro --without-podman
open -a Docker   # Docker Desktop must be running
```

**Everyday loop** — all `astro` commands run from the project directory:

```bash
cd orchestration
astro dev start                    # build + start local Airflow (4 containers)
astro dev pytest tests/dags -a "-v"  # DAG integrity tests (DagBag)
astro dev stop                     # stop when done (astro dev kill = hard reset)
```

- **Airflow UI:** <http://localhost:8080> (Astro's project-scoped proxy also
  serves it at <http://orchestration.localhost:6563>).
- **Dags:** `orchestration/dags/` — currently the `example_astronauts` example
  DAG (`dags/exampledag.py`).
- **Tests:** `orchestration/tests/dags/` — DagBag-based checks: no import
  errors, every DAG has tags and retries.
- **Local-only files:** `.astro/standalone|worktrees|*.local.*` (project local
  state) and `.env` (environment variables) are gitignored; `.astro/config.yaml`
  (project name) **is** committed — Astro uses it to detect the project.
  `airflow_settings.yaml` holds local connections/variables — placeholders
  only, **never put secrets there**.

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
