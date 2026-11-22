#!/usr/bin/env python3
"""Execute snowflake/snowflake_setup.sql.

A deliberately dumb runner (~60 lines) so that "the setup is scripted" is
literally true: the SQL file is the single source of truth, and this only
splits it into statements and executes them in order.

Splitting rule: a statement ends at a ';' that is NOT inside a $$...$$ block,
a '...' string or a -- comment. Everything else is passed through untouched.

    python snowflake/run_sql.py --dry-run     # how many statements, no login
    python snowflake/run_sql.py               # execute

The public key is read from SNOWFLAKE_DLT_DEV_PUBLIC_KEY or, if unset, from the
key directory outside the repo; it is a PUBLIC key, so printing it is harmless
(the private key is never touched here).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

SQL_FILE = pathlib.Path(__file__).with_name("snowflake_setup.sql")
KEY_VALUE_FILE = pathlib.Path(
    "~/.snowflake/keys/github_raw/dlt_dev/rsa_key.pub.b64"
).expanduser()


def split_statements(sql: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    i, n = 0, len(sql)
    in_block = in_string = in_comment = False
    while i < n:
        ch, two = sql[i], sql[i : i + 2]
        if in_comment:
            in_comment = ch != "\n"
            buf.append(ch)
        elif in_block:
            if two == "$$":
                buf.append(two)
                i += 2
                in_block = False
                continue
        elif in_string:
            in_string = ch != "'"
        elif two == "$$":
            buf.append(two)
            i += 2
            in_block = True
            continue
        elif two == "--":
            in_comment = True
        elif ch == "'":
            in_string = True
        elif ch == ";":
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def render(sql: str) -> str:
    key = os.environ.get("SNOWFLAKE_DLT_DEV_PUBLIC_KEY") or KEY_VALUE_FILE.read_text(
        encoding="utf-8"
    )
    return sql.replace("{{ DLT_DEV_PUBLIC_KEY }}", key.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="list statements only")
    parser.add_argument("--role", default="ACCOUNTADMIN")
    args = parser.parse_args()

    statements = split_statements(render(SQL_FILE.read_text(encoding="utf-8")))
    # Drop fragments that are pure comments (the rollback footer is the last one).
    statements = [
        s
        for s in statements
        if any(
            line.strip() and not line.strip().startswith("--")
            for line in s.splitlines()
        )
    ]

    def label(statement: str, width: int = 74) -> str:
        """First line of real code, for readable progress output.

        Comments are stripped only at the START of a statement: a '--' inside a
        $$ block is legitimate SQL and must not be rewritten (an earlier version
        rejoined lines and doubled the characters inside those comments).
        """
        lines = [ln.strip() for ln in statement.splitlines()]
        while lines and (lines[0].startswith("--") or not lines[0]):
            lines.pop(0)
        first = lines[0] if lines else "(comment only)"
        return re.sub(r"\s+", " ", first)[:width]

    if args.dry_run:
        for index, statement in enumerate(statements, 1):
            print(f"{index:2d}. {label(statement)}…")
        print(f"\n{len(statements)} executable statements")
        return 0

    import snowflake.connector as sc

    account = os.environ.get("SNOWFLAKE_ACCOUNT")
    user = os.environ.get("SNOWFLAKE_USER")
    if not (account and user):
        sys.exit("SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER must be set (admin identity)")

    connect = {
        "account": account,
        "user": user,
        "role": args.role,
        "warehouse": "COMPUTE_WH",
    }
    if os.environ.get("SNOWFLAKE_PASSWORD"):
        connect["password"] = os.environ["SNOWFLAKE_PASSWORD"]
    if os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH"):
        connect["private_key_file"] = os.path.expanduser(
            os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]
        )

    with sc.connect(**connect) as con, con.cursor() as cur:
        for index, statement in enumerate(statements, 1):
            cur.execute(statement)
            try:
                rows = cur.fetchall() if cur.description else []
            except sc.Error:  # e.g. statement without a result set
                rows = []
            label = re.sub(r"\s+", " ", statement)[:60]
            print(f"-- {index:2d}. {label}")
            for row in rows:
                print("   ", row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
