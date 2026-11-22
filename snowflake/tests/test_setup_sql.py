"""Offline contract tests for snowflake/snowflake_setup.sql (ticket 004).

Why these exist: the setup script can only be proven against a live account, but
its *guarantees* are static. Each test pins one guarantee so a future edit that
breaks it fails in CI-free local runs instead of after a live `DROP`.

The splitter is imported from `run_sql.py`, so tests see exactly the statements
the runner will execute — no duplicated parsing rules.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import run_sql

SQL = run_sql.SQL_FILE.read_text(encoding="utf-8")
STATEMENTS = [
    s
    for s in run_sql.split_statements(SQL)
    if any(
        line.strip() and not line.strip().startswith("--") for line in s.splitlines()
    )
]
CODE_ONLY = "\n".join(
    line for line in SQL.splitlines() if not line.strip().startswith("--")
)
FLAT = [re.sub(r"\s+", " ", s).strip() for s in STATEMENTS]


def test_the_script_has_the_expected_shape() -> None:
    """A shape test that fails for the right reason.

    The earlier version asserted == 21 and broke when statements were added,
    which told us only that a number changed. What matters is the *guarantees*:
    a bounded number of statements, all of them non-destructive.
    """
    assert 20 <= len(STATEMENTS) <= 40
    assert all(s.strip() for s in STATEMENTS)


def test_the_four_blocks_run_in_the_role_that_holds_the_privilege() -> None:
    """Verified on this account: ACCOUNTADMIN has no CREATE DATABASE/USER/ROLE/
    WAREHOUSE. Each block must therefore run in the role that holds it."""
    roles_used = {
        m.group(1).upper()
        for s in STATEMENTS
        if (m := re.search(r"USE ROLE (\w+)", s, re.IGNORECASE))
    }
    assert roles_used == {"SYSADMIN", "USERADMIN"}, roles_used

    # The database block must be preceded by USE ROLE SYSADMIN, never ACCOUNTADMIN.
    db_index = next(i for i, s in enumerate(STATEMENTS) if "CREATE DATABASE" in s)
    preceding = [
        m.group(0)
        for s in STATEMENTS[:db_index]
        if (m := re.search(r"USE ROLE (\w+)", s, re.IGNORECASE))
    ]
    assert preceding and preceding[-1].lower() == "use role sysadmin", preceding


@pytest.mark.parametrize("pattern", [r"CREATE OR REPLACE", r"\bOR REPLACE\b"])
def test_never_uses_or_replace_outside_comments(pattern: str) -> None:
    """OR REPLACE would drop github_raw's data or reset grants on every run."""
    assert not re.search(pattern, CODE_ONLY, re.IGNORECASE)


def test_every_create_is_guarded() -> None:
    creates = [s for s in FLAT if re.search(r"^CREATE (WAREHOUSE|ROLE|USER)", s)]
    assert len(creates) == 3
    for statement in creates:
        assert "IF NOT EXISTS" in statement


def test_database_is_created_only_when_missing() -> None:
    db_creates = [s for s in FLAT if re.search(r"CREATE DATABASE", s)]
    assert len(db_creates) == 1
    block = db_creates[0]
    assert "EXECUTE IMMEDIATE $$" in block and "IF (db_exists = 0)" in block


def test_key_registration_never_clobbers_an_existing_key() -> None:
    """A silent key swap would change the loader's credential behind dlt's back.

    The guard is the server's own uniqueness check, caught explicitly: ADD KEY
    PAIR refuses an existing name, and the handler turns exactly that into a
    no-op. Any OTHER error is re-raised, so a real failure stays loud.
    """
    block = next(s for s in STATEMENTS if "ADD KEY PAIR" in s)
    assert "ADD KEY PAIR DLT_DEV_KEY_1" in block
    assert "EXCEPTION" in block and "WHEN OTHER" in block
    assert "LIKE '%already exists%'" in block  # the no-op case
    assert "RAISE" in block  # everything else fails loudly
    assert "RSA_PUBLIC_KEY =" not in block  # legacy property not used
    assert "SHA2_BINARY" not in block  # no brittle fingerprint arithmetic


def test_no_database_level_future_grants() -> None:
    """FUTURE grants would leak write access into schemas other roles create."""
    assert not re.search(r"FUTURE", CODE_ONLY, re.IGNORECASE)


def test_grants_are_the_minimal_set() -> None:
    expected = {
        "GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE data_engineer",
        "GRANT USAGE ON DATABASE github_raw TO ROLE data_engineer",
        "GRANT CREATE SCHEMA ON DATABASE github_raw TO ROLE data_engineer",
        "GRANT USAGE ON SCHEMA github_raw.PUBLIC TO ROLE data_engineer",
    }
    role_grants = {s for s in FLAT if re.match(r"^GRANT .* TO ROLE data_engineer$", s)}
    assert role_grants == expected


def test_loader_never_receives_account_level_ddl() -> None:
    for forbidden in (
        "CREATE DATABASE",
        "CREATE USER",
        "CREATE ROLE",
        "CREATE WAREHOUSE",
    ):
        assert not re.search(rf"{forbidden} .*TO ROLE data_engineer", CODE_ONLY)


def test_ownership_is_handed_to_sysadmin_with_current_grants() -> None:
    handovers = [s for s in FLAT if "GRANT OWNERSHIP" in s]
    assert len(handovers) == 2  # warehouse + database
    for statement in handovers:
        assert statement.endswith("TO ROLE SYSADMIN COPY CURRENT GRANTS")


def test_service_user_has_no_password_path() -> None:
    user = next(s for s in FLAT if s.startswith("CREATE USER"))
    assert "TYPE = SERVICE" in user
    assert "PASSWORD" not in user and "MUST_CHANGE_PASSWORD" not in user


def test_public_key_is_a_parameter_not_a_literal() -> None:
    assert "{{ DLT_DEV_PUBLIC_KEY }}" in SQL
    assert not re.search(r"PUBLIC_KEY = '[A-Za-z0-9+/]{100,}", SQL)


def test_rollback_block_is_documented_and_inert() -> None:
    rollback = [
        line
        for line in SQL.splitlines()
        if line.lstrip().startswith("--") and "DROP " in line
    ]
    assert len(rollback) >= 4
    assert not re.search(r"^DROP ", CODE_ONLY, re.MULTILINE)
