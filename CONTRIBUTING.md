# Contributing

`main` is protected: **every change lands through a pull request with at least
1 approval**. Direct pushes are blocked for everyone, admins included.

## The flow

```bash
git checkout -b <type>/<ticket>-<slug>     # e.g. feat/ticket-002-ingestion
# ...work, with tests first (TDD)...
make test && make secret-scan              # must be green BEFORE pushing
git push -u origin HEAD
gh pr create --fill
```

A teammate reviews and approves; then the PR can be merged.

## Rules

1. **TDD.** Write the failing test first, watch it fail, then implement.
2. **Every ticket ships a doc.** Add `docs/tickets/TICKET-XXX-*.md` containing
   the plan and a dated changelog in the same PR as the change.
3. **Governance changes are code changes.** Never click branch protection in
   the GitHub UI — edit `config/governance.toml`, run `make plan`, then
   `make apply`, and let `make test-live` prove the result.
4. **No secrets, ever.** `make secret-scan` runs offline on every push;
   GitHub secret-scanning push protection is the second net.

## Commands

| Command | Purpose |
|---------|---------|
| `make setup` | create venv + install deps |
| `make test` | offline unit tests (fast, no network) |
| `make test-live` | acceptance criteria against the real repo |
| `make plan` | drift report: desired vs actual GitHub state |
| `make apply` | converge GitHub to `config/governance.toml` |
| `make verify-blocking-push` | prove a direct push to `main` is rejected |
