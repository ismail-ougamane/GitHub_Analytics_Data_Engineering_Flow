# GitHub Analytics Data Engineering Flow

End-to-end data engineering project: ingestion, modeling, and analytics over
GitHub activity data — built with a **governance-as-code** foundation where the
repository itself is managed like production infrastructure.

## Why the first ticket is about the repo itself

Every later ticket (ingestion jobs, dbt models, dashboards) depends on a
trustworthy workflow: reviewed changes, protected main, reproducible checks.
That is why [Ticket 001](docs/tickets/TICKET-001-protected-main-branch.md)
protects `main` **with executable acceptance tests** before any pipeline code
lands.

## How we work

- `main` is protected: changes land via pull request with **≥1 approval**
  ([branch protection](config/governance.yaml) is applied by code, not clicks)
- Every ticket ships a `docs/tickets/TICKET-XXX-*.md` file containing its
  **plan** and a dated **changelog**
- Tests drive everything: `make test` (offline, every PR) and
  `make test-live` (asserts real GitHub state)

```bash
make setup        # python venv + deps (uv)
make test         # offline unit + secret-guard tests
make plan         # drift report: desired vs actual GitHub state
make apply        # converge GitHub to config/governance.yaml
make test-live    # acceptance criteria, verified against the real repo
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the review workflow, and
[docs/tickets/README.md](docs/tickets/README.md) for the ticket index.
