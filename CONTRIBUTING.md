# Contributing

`main` is protected by a GitHub ruleset and classic branch protection:
**every change lands through a pull request with at least 1 approval**.
Direct pushes, force pushes and deletions are blocked — admins included.

## The flow

```bash
git checkout -b <type>/<ticket>-<slug>     # e.g. feat/ticket-002-ingestion
# ...work...
git push -u origin HEAD
gh pr create --fill
```

A teammate reviews and approves; then the PR can be merged.

## Rules

1. **Every ticket ships a doc.** Add `docs/tickets/TICKET-XXX-*.md` containing
   the plan and a dated changelog in the same PR as the change.
2. **No secrets, ever.** GitHub secret scanning + push protection is the net.
3. **Protection is deliberate.** Never weaken the `main` ruleset or branch
   protection in the UI; if the rules must change, update the ticket doc in a
   PR explaining why.
