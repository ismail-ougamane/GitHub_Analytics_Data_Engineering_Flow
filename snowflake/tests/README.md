# Verifies ticket 005 (Snowflake provisioning) WITHOUT Snowflake.

The ticket script needs a live account; its *logic* does not. These tests pin the
pieces that a reviewer would otherwise have to take on faith — above all that the
setup file is idempotent and never destructive.

```bash
# from the repo root, with the project env (see README "Provision Snowflake")
uv run --with pytest pytest snowflake/tests -q
```

`test_setup_sql.py` parses `snowflake/snowflake_setup.sql` with the same
splitter the runner uses, so a statement added to the file is covered
automatically.
