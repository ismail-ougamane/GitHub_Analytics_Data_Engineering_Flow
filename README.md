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
