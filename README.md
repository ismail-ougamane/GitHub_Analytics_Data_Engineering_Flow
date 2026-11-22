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

## Provision Snowflake for raw data

The raw layer lives in [`snowflake/`](snowflake/) — see
[TICKET-004](docs/tickets/TICKET-004-snowflake-raw-provisioning.md).

**Objects:** warehouse `COMPUTE_WH` (XSMALL, auto-suspend 60 s), database
`github_raw` (owned by `SYSADMIN`), role `data_engineer`, service user
`dlt_dev` (key-pair only, `TYPE = SERVICE`, so password auth is impossible).

**One-time key pair — outside the repo, never printed:**

```bash
./snowflake/keys/generate_keypair.sh
# -> ~/.snowflake/keys/github_raw/dlt_dev/{rsa_key.p8,rsa_key.pub,rsa_key.pub.b64}
#    (700 dir, 600 files; the script refuses to write inside the repository)
```

**Run the setup (idempotent — safe to re-run):**

```bash
uv sync                                                  # connector + pytest from pyproject.toml

# login: SNOWFLAKE_ACCOUNT is optional if your connection is marked default
snow connection set-default <connection-name>
snow connection test                                     # proves the login works

# 1. dry run: split + parameter render, no login, no DDL
uv run python snowflake/run_sql.py --dry-run             # 21 executable statements

# 2. offline contract tests (no Snowflake at all: no OR REPLACE, no FUTURE grants,
#    exact grant set, key never clobbers an existing one)
uv run pytest snowflake/tests -q

# 3. the real run, twice — the 2nd pass is the idempotency proof
uv run python snowflake/run_sql.py
uv run python snowflake/run_sql.py

# 4. assertions: AC-1/2/3, grant review incl. PUBLIC, JSON snapshot to diff
uv run python snowflake/tests/verify.py admin
uv run python snowflake/tests/verify.py dlt              # positive + negative as dlt_dev
```

`verify.py` asserts outcomes (including the expected error code for every
negative test) and exits non-zero on any violation. Rules this ticket keeps:
`CREATE OR REPLACE` is never used, the private key never leaves
`~/.snowflake/`, and the loader gets no `FUTURE` grants.



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
