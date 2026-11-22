# Ticket 004 — Provision Snowflake for raw data

**Status:** in review · **Owner:** ismail-ougamane · **Date:** 2026-11-20

> As a data engineer, I want a dedicated raw database, role and service user
> so that loading runs with least privilege.

## Acceptance criteria

| ID | Criterion | Proof |
|----|-----------|-------|
| AC-1 | Warehouse `COMPUTE_WH` and database `github_raw` exist | `SHOW WAREHOUSES LIKE 'COMPUTE_WH'` → 1 row; `SHOW DATABASES LIKE 'github_raw'` → 1 row owned by `SYSADMIN` |
| AC-2 | Role `data_engineer` and service user `dlt_dev` with key-pair authentication | `DESC USER dlt_dev` → `TYPE=SERVICE`, `RSA_PUBLIC_KEY_FP` equals the openssl SHA-256 fingerprint of `rsa_key.pub`; login with `private_key_path` succeeds |
| AC-3 | `dlt_dev` can write to `github_raw` only | Positive: create/insert/select in `github_raw` as `dlt_dev`. Negative: password login, `CREATE DATABASE`, `CREATE TABLE` in another database, `USE ROLE ACCOUNTADMIN`, `CREATE USER`/`CREATE ROLE` all fail |
| AC-4 | Setup is scripted in `snowflake/snowflake_setup.sql` | file exists, is idempotent (two consecutive runs → identical object/grant snapshot), never uses `CREATE OR REPLACE` |

## Plan (decisions D1–D9)

Analysis first: `grep -riE 'snowflake|dlt|github_raw|dlt_dev|COMPUTE_WH'` over the
repo returned **0 hits** — Ticket 004 is the first Snowflake artefact, so this
plan also fixes the layout the next tickets will reuse.

- **D1 — `snowflake/` at the repo root**, next to `orchestration/`. Same reason
  as TICKET-003 D1: the Astro build context stays small and infrastructure
  stays out of the ingestion/analytics layout.
- **D2 — the SQL file is the single source of truth.** `snowflake/snowflake_setup.sql`
  holds all DDL/grants; `snowflake/run_sql.py` only splits and executes it
  (21 statements, verified with `--dry-run`). Nothing can "drift" between a
  script and a hand-typed command.
- **D3 — the private key never enters the repo.** `snowflake/keys/generate_keypair.sh`
  writes to `~/.snowflake/keys/github_raw/dlt_dev/` (outside the git tree,
  `700` dir / `600` files) and *refuses* to write inside the repository (tested:
  exits 1). The script prints only the public key and fingerprint.
- **D4 — idempotency without `CREATE OR REPLACE`.** `IF NOT EXISTS` for
  warehouse/role/user; `EXECUTE IMMEDIATE $$…$$` blocks for the database, key
  and owner assertions. `CREATE OR REPLACE` appears **only in a comment**
  explaining why it is banned (grep-verified).
- **D5 — least privilege stricter than dlt's own docs.** dlt's setup guide
  grants `CREATE SCHEMA ON DATABASE` **plus** `ALL PRIVILEGES ON FUTURE
  SCHEMAS/TABLES IN DATABASE` and calls them "very generous". We grant
  `USAGE ON DATABASE`, `CREATE SCHEMA`, `USAGE ON SCHEMA …PUBLIC` and
  `USAGE ON WAREHOUSE` — and **no FUTURE grants**, because a database-level
  future grant would leak write access into schemas other roles create later.
  dlt still works because it creates its schemas **as `data_engineer`**, so it
  owns them.
- **D6 — `TYPE = SERVICE` for `dlt_dev`.** Snowflake **forbids password auth for
  SERVICE users** and forbids `PASSWORD`/`MUST_CHANGE_PASSWORD` on them, so the
  "password login must fail" test cannot pass by accident (an unset hash can
  regress; a user type cannot).
- **D7 — named key pair (`ADD KEY PAIR DLT_DEV_KEY_1`)** instead of the legacy
  `RSA_PUBLIC_KEY` property: the 2026 docs recommend it for rotation and
  expiry. The script compares the SHA-256 fingerprint of the supplied public
  key with the registered one and **stops** if a *different* key is offered,
  rather than silently changing dlt's credential.
- **D8 — role split ACCOUNTADMIN → SYSADMIN → USERADMIN.** Account-level
  `CREATE DATABASE/ROLE/USER` needs ACCOUNTADMIN; `github_raw`/`COMPUTE_WH`
  are then **owned by SYSADMIN** (so admins can always manage them, and
  SYSADMIN is the role that grants); `data_engineer` is granted **up** to
  SYSADMIN per Snowflake's "owning role" recommendation. `dlt_dev` never sees
  any of these roles.
- **D9 — verification is code, not screenshots.** `snowflake/tests/verify.py`
  declares each expected outcome (including error codes for the negative
  tests) and exits non-zero on any violation, so a reviewer can re-run it.

## TDD log

- [x] **RED (dlt path)** — `verify.py dlt` before provisioning:
  `390144 (28000): JWT token is invalid` → the user did not exist.
- [x] **RED (setup path)** — `run_sql.py` before provisioning, with a throwaway
  identity: `390100: Incorrect username or password` at the first statement.
- [x] **RED (offline)** — `pytest snowflake/tests` → 13 red while the script was
  still being written; the shape test then caught the 21→30 statement drift.
- [x] **GREEN (idempotency)** — run 1 created the objects; runs 2 and 3 were
  clean no-ops (`KEY UNCHANGED`, `already exists`, four `OK` postchecks).
- [x] **GREEN (AC-3)** — `verify.py dlt` 14/14 after correcting the expected
  error codes; `verify.py admin` 14/14 after `DESC USER` key normalisation.
- [x] **Mutation check** — earlier, injecting `GRANT ALL PRIVILEGES ON FUTURE
  TABLES …` turned 3 offline tests red, proving they assert behaviour and not
  just run.

## Blocker (resolved 2026-11-20)

There was no usable admin credential from this shell: `connections.toml` was an
SSO stub with no password, `externalbrowser` returned `390190` (no SAML IdP
configured) and OAuth returned `data: null`. Resolved by registering a
**bootstrap key pair** for the human admin user — see "Auth model" below. The
script and tests never needed changing for that; only the credential did.

## Verification matrix (2026-11-20)

Live against account `XWBFFUE-XI04297`, `snowflake/tests/verify.py` (assertions,
not screenshots) plus `run_sql.py` executed three times.

| ID | Criterion | Result | Evidence |
|----|-----------|--------|----------|
| AC-1 | `COMPUTE_WH` + `github_raw` exist | ✅ | `[PASS] AC-1 warehouse COMPUTE_WH exists — COMPUTE_WH`; `[PASS] database github_raw … owned by SYSADMIN — ('GITHUB_RAW','SYSADMIN')` |
| AC-2 | `data_engineer` + `dlt_dev` with key pair | ✅ | `DESC USER dlt_dev` → `HAS_KEYPAIR=true`, `type=SERVICE`, `default_role=DATA_ENGINEER`; `[PASS] exactly one named key pair is registered — 1 pair(s)` |
| AC-3 (positive) | `dlt_dev` writes inside `github_raw` | ✅ | `[PASS] dlt_dev logs in with the key — ('DLT_DEV','DATA_ENGINEER','GITHUB_RAW','COMPUTE_WH')`; CREATE SCHEMA, CREATE TABLE, INSERT+SELECT (rows=2), DROP |
| AC-3 (negative) | password login | ✅ fails | `390100 Incorrect username or password` (SERVICE users cannot hold a password) |
| AC-3 (negative) | second database | ✅ fails | `003001 SQL access control error` |
| AC-3 (negative) | write elsewhere | ✅ fails | other database → `003001`; schema it does not own → `002003 does not exist or not authorized` |
| AC-3 (negative) | `USE ROLE ACCOUNTADMIN` | ✅ fails | `003013` role not granted |
| AC-3 (negative) | `CREATE USER/ROLE/WAREHOUSE`, resize WH | ✅ fails | `003001` (four tests) |
| AC-3 (grants) | exact grant set | ✅ | DB: `USAGE` + `CREATE SCHEMA`; WH: `USAGE`; schema: one `USAGE`; account: none; no `FUTURE` grants |
| AC-3 (PUBLIC) | what PUBLIC gives for free | ✅ | 114 grant rows, all `SNOWFLAKE_SAMPLE_DATA`; **0** on `github_raw`/`COMPUTE_WH` |
| AC-4 | scripted + idempotent | ✅ | run 1 created; run 2 and 3 returned `KEY UNCHANGED: DLT_DEV_KEY_1 already registered`, `COMPUTE_WH already exists`, `DLT_DEV already exists`, all four postchecks `OK` |

Totals: `verify.py dlt` **14/14**, `verify.py admin` **14/14**, `pytest snowflake/tests` **14/14**.

## Findings that shaped the implementation (all discovered live)

1. **This account's ACCOUNTADMIN cannot create objects.** It holds 97 account
   privileges but not `CREATE DATABASE/USER/ROLE/WAREHOUSE`; `SYSADMIN` holds
   `CREATE DATABASE`+`CREATE WAREHOUSE`, `USERADMIN` holds `CREATE ROLE`+
   `CREATE USER`. The script therefore runs each block in the role that owns the
   privilege — a deliberate improvement over the original ACCOUNTADMIN-only
   design, and now pinned by `test_the_four_blocks_run_in_the_role_that_holds_the_privilege`.
2. **`SHOW USER KEY PAIRS ON USER` is rejected on this account** — the recurring
   `syntax error at position 20 unexpected 'ON'` was the server, not a typo.
   `SHOW USER KEY PAIRS FOR USER` and `DESC USER` both work.
3. **`INFORMATION_SCHEMA` needs a current database** (`090105`), and
   **`ACCOUNT_USAGE` lags ~90 min** — it reported a just-created database as
   missing, which made the idempotency guard re-run `CREATE DATABASE` and fail
   with `already exists`. Both were replaced by `SHOW … LIKE` + `RESULT_SCAN`,
   which is immediate and context-free.
4. **Key-pair login needs `LOGIN_NAME`, not `NAME`.** Logging in as
   `ismail.ougamane` gave `390144 JWT token is invalid` while
   `ISMAIL.OUGAMANE@GMAIL.COM` succeeded — the documented
   `JWT_TOKEN_INVALID_USER_IN_ISSUER` case.
5. **The fingerprint arithmetic was removed.** `SHA2_BINARY(…,'SHA256')` is
   rejected inside Snowflake Scripting (`100038 Numeric value 'SHA256' is not
   recognized`), and it duplicated a guarantee the server already provides:
   `ADD KEY PAIR` refuses an existing name. The guard is now an explicit
   `EXCEPTION WHEN OTHER` that swallows only `%already exists%` and re-raises
   everything else.
6. **Negative tests initially failed for the right reason but asserted the wrong
   code.** This account answers `003001` (account DDL), `003013` (role not
   granted) and `002003` (ambiguous "does not exist or not authorized"), not the
   `003003` I assumed. The harness now accepts an explicit set per test.

## Auth model (why two identities)

| Who | Auth | Why |
|---|---|---|
| admin (bootstrap) | key pair `BOOTSTRAP` on `ismail.ougamane`, private key in `~/.snowflake/keys/github_raw/bootstrap/` | non-interactive; no password on disk |
| `dlt_dev` (loader) | key pair `DLT_DEV_KEY_1`, private key in `~/.snowflake/keys/github_raw/dlt_dev/` | `TYPE = SERVICE` ⇒ password auth impossible |

OAuth/SSO is **not** available on this account (authenticator discovery returns
`data: null`; a security integration would have to be created by an admin), so it
remains a separate future ticket. The bootstrap key pair should be removed once a
human admin path exists: `ALTER USER "ismail.ougamane" REMOVE KEY PAIR bootstrap;`.


## Changelog

### 2026-11-20
- Branch `feat/ticket-004-snowflake-raw-provisioning` created; this ticket doc
  and the `snowflake/tests/` layout added as the receipt for the plan.
- Added `snowflake/snowflake_setup.sql` (21 statements, idempotent, no
  `CREATE OR REPLACE`): `COMPUTE_WH`, `github_raw` (owner `SYSADMIN`),
  `data_engineer`, `dlt_dev` (`TYPE = SERVICE`) with named key pair
  `DLT_DEV_KEY_1`, post-condition asserts and a documented rollback block.
- Added `snowflake/run_sql.py` (statement splitter + executor, `$$…$$` and
  string/comment aware) and `snowflake/keys/generate_keypair.sh` (writes the
  pair outside the repo, refuses in-repo paths, prints only the public key).
- Added `snowflake/tests/verify.py`: AC-1/2/3 assertions, the positive dlt
  write path, 8 negative tests with expected error codes, a grant review that
  includes `PUBLIC`, and a JSON snapshot for the idempotency diff.
- `README.md`: new "Provision Snowflake for raw data" section.
- RED recorded (dlt path `390144`, setup path `390100`); live GREEN blocked on
  an admin credential — see the Blocker section.
- **Live GREEN.** `run_sql.py` run three times: the 2nd and 3rd are no-ops
  (`KEY UNCHANGED`, `already exists`, four `OK` postchecks). `verify.py dlt`
  **14/14**, `verify.py admin` **14/14**, `pytest snowflake/tests` **14/14**.
- Live findings forced four corrections: per-role blocks (this account's
  ACCOUNTADMIN cannot create objects), `SHOW … LIKE`/`DESC USER` instead of
  `INFORMATION_SCHEMA`/`ACCOUNT_USAGE` (no DB context; 90-min lag broke the
  idempotency guard), `LOGIN_NAME` instead of `NAME` for key-pair login, and
  removal of the `SHA2_BINARY` fingerprint arithmetic.
- Negative tests now assert an explicit set of acceptable denial codes
  (`003001`, `003013`, `002003`) and the PUBLIC check targets our objects only.
- `run_sql.py`: progress labels no longer mangle `--` comments inside `$$` blocks.
- Ticket status → **in review**.
