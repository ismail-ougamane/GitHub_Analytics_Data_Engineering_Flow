#!/usr/bin/env python3
"""Assertions for ticket 005 — "Provision Snowflake for raw data".

Run from the repo root:

    /tmp/sfvenv/bin/python snowflake/tests/verify.py admin   # needs admin creds
    /tmp/sfvenv/bin/python snowflake/tests/verify.py dlt     # key-pair only

Why a script instead of copying SQL output into the ticket: a test must be able
to FAIL. Each check declares the expected outcome, and the exit code is non-zero
if any expectation is violated, so the proof is reproducible by a reviewer.

No secret is read from a file here: the dlt checks read the private key path
from SNOWFLAKE_PRIVATE_KEY_PATH (default: ~/.snowflake/keys/github_raw/dlt_dev).
The admin checks authenticate with the Snowflake CLI connection settings
(~/.snowflake/connections.toml) or SNOWFLAKE_* environment variables.
"""

from __future__ import annotations

import json
import os
import sys
import traceback

ACCOUNT = os.environ.get("SNOWFLAKE_ACCOUNT", "")
USER = os.environ.get("SNOWFLAKE_USER", "")
DATABASE = "github_raw"
WAREHOUSE = "COMPUTE_WH"
ROLE = "data_engineer"
SERVICE_USER = "dlt_dev"
# LOGIN_NAME for the login call; NAME for object references in SQL.
SERVICE_USER_LOGIN = os.environ.get("SNOWFLAKE_DLT_LOGIN_NAME", SERVICE_USER)
KEY_PATH = os.path.expanduser(
    os.environ.get(
        "SNOWFLAKE_PRIVATE_KEY_PATH", "~/.snowflake/keys/github_raw/dlt_dev/rsa_key.p8"
    )
)

RESULTS: list[tuple[str, str, str]] = []


class AdminCredentialMissing(RuntimeError):
    """No admin credential configured for this shell — see the ticket blocker."""


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(("PASS" if ok else "FAIL", name, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


# --------------------------------------------------------------------------- #
# connections
# --------------------------------------------------------------------------- #
def _snowflake():
    try:
        import snowflake.connector  # noqa: F401
    except ModuleNotFoundError:
        sys.exit("snowflake-connector-python is not installed in this interpreter")


def connect_admin():
    """Admin session. Credentials come from env / the CLI config store only."""
    _snowflake()
    import snowflake.connector as sc

    kwargs = {"account": ACCOUNT or None, "user": USER or None}
    if os.environ.get("SNOWFLAKE_PASSWORD"):  # never written to disk
        kwargs["password"] = os.environ["SNOWFLAKE_PASSWORD"]
    elif os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH"):
        kwargs["private_key_file"] = os.path.expanduser(
            os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]
        )
    else:
        # Not an error for commands that never authenticate (e.g. --dry-run);
        # checks_admin() reports AdminCredentialMissing when it is needed.
        return None
    return sc.connect(**{k: v for k, v in kwargs.items() if v is not None})


def connect_dlt():
    """Service-user session, key-pair only. Cannot use a password by design.

    Key-pair login requires the user's LOGIN_NAME, not its NAME: Snowflake
    embeds the identity in the JWT issuer and resolves it as a login name. A
    NAME here fails with 390144 "JWT token is invalid" even though the key is
    registered (documented as JWT_TOKEN_INVALID_USER_IN_ISSUER).
    """
    _snowflake()
    import snowflake.connector as sc

    return sc.connect(
        account=ACCOUNT,
        user=SERVICE_USER_LOGIN,
        private_key_file=KEY_PATH,
        role=ROLE,
        warehouse=WAREHOUSE,
        database=DATABASE,
        session_parameters={"QUERY_TAG": "ticket-005-verify"},
    )


def one(cur, sql: str):
    cur.execute(sql)
    return cur.fetchone()


def expect_error(
    name: str, cur, sql: str, code: str | tuple[str, ...], needle: str = ""
) -> None:
    """The statement MUST fail with one of the given Snowflake error codes.

    Codes are matched as an explicit set rather than one string: this account
    answers 003001 for account-level DDL, 003013 for a role not granted, and
    002003 for "does not exist or not authorized" — all legitimate denials.
    """
    codes = (code,) if isinstance(code, str) else code
    try:
        cur.execute(sql)
        rows = cur.fetchall() if cur.description else []
        record(name, False, f"statement unexpectedly SUCCEEDED (rows={rows!r})")
    except Exception as exc:  # noqa: BLE001 - the failure is the expectation
        msg = str(exc)
        ok = any(c in msg for c in codes) and (
            needle.lower() in msg.lower() if needle else True
        )
        record(name, ok, msg.splitlines()[0][:160])


# --------------------------------------------------------------------------- #
# dlt_dev: positive — can write inside github_raw
# --------------------------------------------------------------------------- #
def checks_dlt_positive() -> None:
    try:
        with connect_dlt() as con, con.cursor() as cur:
            ident = one(
                cur,
                "SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), "
                "CURRENT_WAREHOUSE()",
            )
            record(
                "dlt_dev logs in with the key and gets its default context",
                ident[1] == ROLE.upper()
                and ident[2] == DATABASE.upper()
                and ident[3] == WAREHOUSE.upper(),
                f"{ident}",
            )

            # dlt creates its own schema on first load -> same privilege path.
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {DATABASE}.smoke_test")
            record("dlt_dev can CREATE SCHEMA in github_raw", True)

            cur.execute(
                f"""CREATE TABLE IF NOT EXISTS {DATABASE}.smoke_test.t_probe (
                        id        NUMBER,
                        payload   VARCHAR,
                        loaded_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
                    )"""
            )
            record("dlt_dev can CREATE TABLE in a schema it owns", True)

            cur.execute(
                f"INSERT INTO {DATABASE}.smoke_test.t_probe (id, payload) "
                "VALUES (1, 'airflow'), (2, 'github')"
            )
            cur.execute(
                f"SELECT COUNT(*), MIN(payload) FROM {DATABASE}.smoke_test.t_probe"
            )
            count, first = cur.fetchone()
            record(
                "dlt_dev can INSERT and SELECT back",
                count == 2,
                f"rows={count}, first={first}",
            )

            # Idempotent cleanup: the schema is ours, so dropping it is allowed.
            cur.execute(f"DROP SCHEMA IF EXISTS {DATABASE}.smoke_test")
            record("dlt_dev can DROP the schema it owns (cleanup)", True)
    except Exception as exc:  # noqa: BLE001 - report, do not crash the suite
        record("dlt_dev connect + write path", False, str(exc).splitlines()[0][:160])


# --------------------------------------------------------------------------- #
# dlt_dev: negative — every one of these MUST fail
# --------------------------------------------------------------------------- #
def checks_dlt_negative() -> None:
    with connect_dlt() as con, con.cursor() as cur:
        # 1. Password login is impossible: SERVICE users cannot authenticate
        #    with a password at all, so this is enforced by the account.
        import snowflake.connector as sc

        try:
            sc.connect(
                account=ACCOUNT, user=SERVICE_USER, password="not-a-password"
            ).close()
            record("password login for dlt_dev fails", False, "login SUCCEEDED")
        except Exception as exc:  # noqa: BLE001
            record(
                "password login for dlt_dev fails", True, str(exc).splitlines()[0][:120]
            )

        # 2. Second database: CREATE DATABASE is account-level, never granted.
        #    This account answers 003001 (not 003003) for account-level DDL.
        expect_error(
            "dlt_dev cannot CREATE DATABASE",
            cur,
            "CREATE DATABASE dlt_should_not_exist",
            code="003001",
        )

        # 3. Write outside github_raw. A database it cannot see at all answers
        #    002003 "does not exist or not authorized" (deliberately ambiguous);
        #    a readable but unwritable one answers 003001.
        expect_error(
            "dlt_dev cannot CREATE TABLE in another database",
            cur,
            "CREATE TABLE snowflake_learning_db.information_schema.t_should_not_exist (id NUMBER)",
            code=("002003", "003001", "003003"),
        )

        # 4. Write elsewhere inside github_raw: a schema it does not own and
        #    was not granted on. SYSADMIN creates it, dlt_dev must be denied.
        expect_error(
            "dlt_dev cannot CREATE TABLE in a schema it does not own",
            cur,
            f"CREATE TABLE {DATABASE}.sysadmin_schema.t_should_not_exist (id NUMBER)",
            code=("002003", "003001", "003003"),
        )

        # 5. Privilege escalation via a system role -> 003013 (role not granted).
        expect_error(
            "dlt_dev cannot USE ROLE ACCOUNTADMIN",
            cur,
            "USE ROLE ACCOUNTADMIN",
            code="003013",
        )

        # 6. Account-level DDL.
        for statement, object_ in (
            ("CREATE USER dlt_should_not_exist", "USER"),
            ("CREATE ROLE dlt_should_not_exist", "ROLE"),
            ("CREATE WAREHOUSE dlt_should_not_exist", "WAREHOUSE"),
        ):
            expect_error(
                f"dlt_dev cannot CREATE {object_}",
                cur,
                statement,
                code="003001",
            )

        # 7. Warehouse management (USAGE is not OPERATE).
        expect_error(
            "dlt_dev cannot RESIZE the warehouse",
            cur,
            f"ALTER WAREHOUSE {WAREHOUSE} SET WAREHOUSE_SIZE = 'LARGE'",
            code="003001",
        )


# --------------------------------------------------------------------------- #
# admin: object inventory, grant review (incl. PUBLIC) and idempotency snapshot
# --------------------------------------------------------------------------- #
EXPECTED_DB_GRANTS = {("USAGE", "DATABASE"), ("CREATE SCHEMA", "DATABASE")}
EXPECTED_WH_GRANTS = {("USAGE", "WAREHOUSE")}


def checks_admin() -> None:
    admin = connect_admin()
    if admin is None:
        raise AdminCredentialMissing(
            "no admin credential: set SNOWFLAKE_PASSWORD (hidden prompt) or "
            "SNOWFLAKE_PRIVATE_KEY_PATH, plus SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER"
        )
    with admin as con, con.cursor() as cur:
        cur.execute("USE ROLE ACCOUNTADMIN")

        # --- objects exist -------------------------------------------------
        # SHOW + RESULT_SCAN rather than INFORMATION_SCHEMA: INFORMATION_SCHEMA
        # is scoped to the CURRENT database, and this session has none.
        cur.execute(f"SHOW WAREHOUSES LIKE '{WAREHOUSE}'")
        rows = cur.fetchall()
        wh = rows[0] if rows else None
        record("AC-1 warehouse COMPUTE_WH exists", wh is not None, f"{wh and wh[0]}")

        cur.execute(f"SHOW DATABASES LIKE '{DATABASE}'")
        rows = cur.fetchall()
        db = rows[0] if rows else None
        record(
            "AC-1 database github_raw exists and is owned by SYSADMIN",
            db is not None and db[5] == "SYSADMIN",
            f"{db and (db[1], db[5])}",
        )

        cur.execute(f"SHOW USERS LIKE '{SERVICE_USER}'")
        rows = cur.fetchall()
        usr = rows[0] if rows else None
        # SHOW USERS columns: name, created_on, login_name, display_name, ...
        # type/default_* come from DESC USER, so read them there.
        record("AC-2 service user dlt_dev exists", usr is not None, f"{usr and usr[0]}")

        cur.execute(f"DESC USER {SERVICE_USER}")
        props = {str(r[0]).lower(): r[1] for r in cur.fetchall()}
        record(
            "AC-2 dlt_dev is TYPE=SERVICE with role/warehouse/namespace defaults",
            props.get("type") == "SERVICE"
            and props.get("default_role") == ROLE.upper()
            and props.get("default_warehouse") == WAREHOUSE.upper()
            and (props.get("default_namespace") or "")
            .upper()
            .startswith(DATABASE.upper()),
            f"type={props.get('type')} role={props.get('default_role')} "
            f"wh={props.get('default_warehouse')} ns={props.get('default_namespace')}",
        )
        record(
            "AC-2 dlt_dev has a public key registered (HAS_KEYPAIR)",
            props.get("has_keypair") == "true",
            f"has_keypair={props.get('has_keypair')}",
        )

        cur.execute(f"SHOW USER KEY PAIRS FOR USER {SERVICE_USER}")
        pairs = cur.fetchall()
        record(
            "AC-2 exactly one named key pair is registered",
            len(pairs) == 1,
            f"{len(pairs)} pair(s)",
        )

        # --- AC-3: exactly the grant set we designed, nothing more ---------
        cur.execute(f"SHOW GRANTS TO ROLE {ROLE}")
        grants = {(g[1], g[2]) for g in cur.fetchall()}  # (privilege, granted_on)
        db_grants = {g for g in grants if g[1] == "DATABASE"}
        wh_grants = {g for g in grants if g[1] == "WAREHOUSE"}
        schema_grants = {g for g in grants if g[1] == "SCHEMA"}
        account_grants = {g for g in grants if g[1] == "ACCOUNT"}
        record(
            "AC-3 database-level grants are exactly USAGE + CREATE SCHEMA",
            db_grants == EXPECTED_DB_GRANTS,
            f"{sorted(db_grants)}",
        )
        record(
            "AC-3 warehouse grants are exactly USAGE",
            wh_grants == EXPECTED_WH_GRANTS,
            f"{sorted(wh_grants)}",
        )
        record(
            "AC-3 schema-level grants are USAGE only (github_raw.PUBLIC)",
            len(schema_grants) == 1 and all(g[0] == "USAGE" for g in schema_grants),
            f"{sorted(schema_grants)}",
        )
        record(
            "AC-3 no account-level privileges (no CREATE DATABASE/USER/ROLE)",
            account_grants == set(),
            f"{sorted(account_grants)}",
        )
        record(
            "AC-3 no FUTURE grants at database level",
            not any("FUTURE" in g[0].upper() for g in grants),
            "",
        )

        # --- what does PUBLIC give for free? --------------------------------
        # PUBLIC is auto-granted to every user and every role, so the question
        # is not "does it hold anything" (a fresh account grants it USAGE on
        # SNOWFLAKE_SAMPLE_DATA) but "does it reach OUR objects".
        cur.execute("SHOW GRANTS TO ROLE PUBLIC")
        public_grants = cur.fetchall()
        ours = [
            g
            for g in public_grants
            if DATABASE.upper() in str(g[3] or "").upper()
            or WAREHOUSE.upper() in str(g[3] or "").upper()
        ]
        record(
            "PUBLIC holds no grant on github_raw or COMPUTE_WH",
            ours == [],
            f"{len(public_grants)} rows total (sample data included), {len(ours)} on our objects",
        )

        cur.execute(f"SHOW GRANTS OF ROLE {ROLE}")
        names = {(g[2], g[3]) for g in cur.fetchall()}  # (granted_to, grantee_name)
        record(
            "role data_engineer granted only to SYSADMIN and dlt_dev",
            names == {("ROLE", "SYSADMIN"), ("USER", SERVICE_USER.upper())},
            f"{sorted(names)}",
        )

        # --- fixture for the cross-schema negative test ---------------------
        cur.execute("USE ROLE SYSADMIN")
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {DATABASE}.sysadmin_schema")
        record("fixture: github_raw.sysadmin_schema owned by SYSADMIN", True)
        cur.execute("USE ROLE ACCOUNTADMIN")

        # --- idempotency snapshot (JSON, diffed between two runs) ----------
        snap: dict[str, object] = {}
        cur.execute(f"SHOW GRANTS TO ROLE {ROLE}")
        snap["grants_to_role"] = sorted(
            tuple(str(x) for x in r[1:3]) for r in cur.fetchall()
        )
        cur.execute(f"SHOW GRANTS OF ROLE {ROLE}")
        snap["grants_of_role"] = sorted(
            tuple(str(x) for x in r[2:4]) for r in cur.fetchall()
        )
        cur.execute(f"SHOW USER KEY PAIRS FOR USER {SERVICE_USER}")
        snap["key_pairs"] = sorted(
            tuple(str(x) for x in r[0:2]) for r in cur.fetchall()
        )
        cur.execute(f"DESC USER {SERVICE_USER}")
        props = {str(r[0]).lower(): r[1] for r in cur.fetchall()}
        snap["user"] = {
            k: props.get(k)
            for k in ("type", "default_role", "default_warehouse", "default_namespace")
        }
        snap["has_password"] = props.get("has_password")
        cur.execute(f"SHOW WAREHOUSES LIKE '{WAREHOUSE}'")
        w = cur.fetchall()[0]
        snap["warehouse"] = {"name": w[0], "size": w[1]}
        cur.execute(f"SHOW DATABASES LIKE '{DATABASE}'")
        d = cur.fetchall()[0]
        snap["database"] = {"name": d[1], "owner": d[5]}
        cur.execute(
            f"SELECT SCHEMA_NAME FROM {DATABASE}.INFORMATION_SCHEMA.SCHEMATA "
            "ORDER BY SCHEMA_NAME"
        )
        snap["schemas"] = [r[0] for r in cur.fetchall()]
        print("=== SNAPSHOT ===")
        print(json.dumps(snap, indent=2, sort_keys=True, default=str))


# --------------------------------------------------------------------------- #
def main() -> int:
    scope = sys.argv[1] if len(sys.argv) > 1 else "all"
    try:
        if scope in ("dlt", "all"):
            checks_dlt_positive()
            checks_dlt_negative()
        if scope in ("admin", "all"):
            checks_admin()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 2
    failed = [r for r in RESULTS if r[0] == "FAIL"]
    print(f"\n{len(RESULTS) - len(failed)} passed, {len(failed)} failed")
    for _status, name, detail in failed:
        print(f"  FAIL {name} — {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
