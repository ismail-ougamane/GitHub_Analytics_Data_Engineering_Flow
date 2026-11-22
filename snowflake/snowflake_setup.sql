-- =============================================================================
-- snowflake/snowflake_setup.sql
-- Ticket: docs/tickets/TICKET-004-snowflake-raw-provisioning.md
--
-- Provisions the raw layer for the GitHub (Airflow repo) metadata pipeline:
--   warehouse COMPUTE_WH · database github_raw · role data_engineer
--   service user dlt_dev (key-pair authentication, no password possible)
--
-- CONTRACT
--   * Idempotent: running it twice leaves an identical object/grant snapshot.
--   * CREATE OR REPLACE is NEVER used: it would drop the database (and its
--     data) or reset a user's/role's grants.
--   * Least privilege: dlt_dev -> data_engineer -> github_raw only.
--   * No secret is stored in this file or in git. The public key is a PARAMETER;
--     the private key never leaves ~/.snowflake/keys/github_raw/dlt_dev/.
--
-- HOW TO RUN  (snowflake CLI, from the repo root)
--   snow sql -f snowflake/snowflake_setup.sql \
--     -D DLT_DEV_PUBLIC_KEY="$(cat ~/.snowflake/keys/github_raw/dlt_dev/rsa_key.pub.b64)" \
--     -c <your-admin-connection>
--
-- ROLE MODEL USED HERE (why each role runs a block)
--   Verified on this account (2026-11-20): ACCOUNTADMIN holds 97 account-level
--   privileges but NOT CREATE DATABASE / CREATE WAREHOUSE / CREATE USER /
--   CREATE ROLE. Those are delegated to the system roles below, so each block
--   must run in the role that actually owns the privilege:
--     SYSADMIN   CREATE DATABASE, CREATE WAREHOUSE  -> owns COMPUTE_WH, github_raw
--     USERADMIN  CREATE ROLE, CREATE USER           -> owns data_engineer, dlt_dev
--   ACCOUNTADMIN keeps the read-only assertions at the end.
--   data_engineer the loader role; it owns every schema dlt creates.
-- =============================================================================


-- =============================================================================
-- 1. WAREHOUSE  COMPUTE_WH
--    A virtual warehouse is the compute cluster that runs queries. It stores no
--    data and bills credits only while running: suspend after 60 s of idle and
--    start suspended => cost stays at zero when nobody loads.
--    Runs as SYSADMIN: it holds CREATE WAREHOUSE on this account (ACCOUNTADMIN
--    does not) and becomes the warehouse owner, so admins keep control of it.
-- =============================================================================
USE ROLE SYSADMIN;

CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH
  WAREHOUSE_SIZE      = 'XSMALL'
  AUTO_SUSPEND        = 60
  AUTO_RESUME         = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT             = 'Shared compute for github_raw loads (dlt) and queries';

-- COPY CURRENT GRANTS keeps grants that already exist on the warehouse, so a
-- re-run cannot wipe access that was granted elsewhere.
GRANT OWNERSHIP ON WAREHOUSE COMPUTE_WH TO ROLE SYSADMIN COPY CURRENT GRANTS;

-- =============================================================================
-- 2. DATABASE  github_raw
--    Database -> schema -> table is the container hierarchy; privileges are
--    granted on each level. 1 day of Time Travel is enough for a raw landing
--    zone and keeps storage cost minimal.
--
--    `CREATE DATABASE` is wrapped in a block rather than written as
--    "CREATE DATABASE IF NOT EXISTS" so that we can *assert the owner* right
--    after: if someone else created github_raw, every GRANT below (issued by
--    SYSADMIN) would fail or silently do nothing.
-- =============================================================================
USE ROLE SYSADMIN;

EXECUTE IMMEDIATE $$
DECLARE
  db_exists NUMBER DEFAULT 0;
  stmt VARCHAR;
BEGIN
  -- Existence check without INFORMATION_SCHEMA (needs a current database) and
  -- without ACCOUNT_USAGE (up to 90 min of latency: it reported the database as
  -- missing seconds after creation, so the guard re-ran CREATE and failed with
  -- "Object 'GITHUB_RAW' already exists"). SHOW DATABASES LIKE is immediate.
  SHOW DATABASES LIKE 'github_raw';
  SELECT COUNT(*) INTO :db_exists FROM TABLE(RESULT_SCAN(LAST_QUERY_ID(-1)));

  IF (db_exists = 0) THEN
    CREATE DATABASE github_raw
      DATA_RETENTION_TIME_IN_DAYS = 1
      COMMENT = 'Raw landing zone for GitHub (Airflow repo) metadata';
  END IF;
END;
$$;

GRANT OWNERSHIP ON DATABASE github_raw TO ROLE SYSADMIN COPY CURRENT GRANTS;

-- Assertion: any owner other than SYSADMIN => stop the script here.
EXECUTE IMMEDIATE $$
DECLARE
  db_owner VARCHAR;
BEGIN
  SHOW DATABASES LIKE 'github_raw';
  SELECT "owner" INTO :db_owner FROM TABLE(RESULT_SCAN(LAST_QUERY_ID(-1)));
  IF (db_owner <> 'SYSADMIN') THEN
    RETURN 'STOP: github_raw is owned by ' || db_owner || ', expected SYSADMIN';
  END IF;
  RETURN 'OK: github_raw owned by ' || db_owner;
END;
$$;

-- =============================================================================
-- 3. ROLE  data_engineer
--    A role is a named bundle of privileges; users get no privilege directly.
--    Granting it UP to SYSADMIN (Snowflake's recommendation for "owning roles")
--    lets system admins manage everything this role owns and grants.
-- =============================================================================
USE ROLE USERADMIN;
CREATE ROLE IF NOT EXISTS data_engineer
  COMMENT = 'Loader role: write access to github_raw only';
GRANT ROLE data_engineer TO ROLE SYSADMIN;

-- =============================================================================
-- 4. GRANTS ON github_raw  — the least-privilege core
--    Issued as SYSADMIN (owner of the database and the warehouse).
--
--    USAGE on database     : resolve/see the database and its schemas.
--    CREATE SCHEMA         : dlt creates its dataset schemas on first load. It
--                            creates them AS data_engineer, so data_engineer
--                            OWNS them and needs no further grant to build
--                            tables inside.
--    USAGE on warehouse    : run queries on the compute; cannot resize/drop it.
--    USAGE on PUBLIC schema: dlt's DEFAULT_NAMESPACE points at github_raw.public;
--                            creation of a table needs USAGE on that schema.
--
--    DELIBERATELY NOT GRANTED (dlt's docs propose these — we do better):
--      CREATE DATABASE on account        -> a second database becomes possible.
--      ALL PRIVILEGES ON FUTURE SCHEMAS/TABLES IN DATABASE
--                                        -> leaks write access into schemas that
--                                           OTHER roles create later.
--      MONITOR/OPERATE on the warehouse  -> management, not usage.
--    Small set = the negative tests in tests/ are meaningful.
-- =============================================================================
USE ROLE SYSADMIN;
GRANT USAGE ON WAREHOUSE COMPUTE_WH       TO ROLE data_engineer;
GRANT USAGE ON DATABASE  github_raw       TO ROLE data_engineer;
GRANT CREATE SCHEMA ON DATABASE github_raw TO ROLE data_engineer;
GRANT USAGE ON SCHEMA github_raw.PUBLIC   TO ROLE data_engineer;

-- =============================================================================
-- 5. SERVICE USER  dlt_dev  + named key pair
--
--    TYPE = SERVICE: Snowflake itself refuses password logins for this user and
--    forbids PASSWORD / MUST_CHANGE_PASSWORD on it. The "password login must
--    fail" test therefore cannot pass by accident (e.g. an unset hash).
--
--    Key-pair auth needs a parameter supplied at run time:
--        DLT_DEV_PUBLIC_KEY = base64 DER of the public key, WITHOUT the
--        "-----BEGIN PUBLIC KEY-----" delimiters, single line:
--        openssl rsa -pubin -in rsa_key.pub -outform DER | base64 | tr -d '\n'
--
--    ADD KEY PAIR is the current, rotation-friendly form; the legacy
--    RSA_PUBLIC_KEY property supports neither expiry nor role restriction.
-- =============================================================================
USE ROLE USERADMIN;

CREATE USER IF NOT EXISTS dlt_dev
  TYPE              = SERVICE
  DEFAULT_ROLE      = data_engineer
  DEFAULT_WAREHOUSE = COMPUTE_WH
  DEFAULT_NAMESPACE = 'github_raw.public'
  COMMENT           = 'dlt loader for github_raw - key-pair authentication only';

GRANT ROLE data_engineer TO USER dlt_dev;

-- Key registration, idempotent WITHOUT fingerprint arithmetic.
-- An earlier version computed the SHA-256 fingerprint inline; Snowflake
-- Scripting rejects that expression (100038 "Numeric value 'SHA256' is not
-- recognized"), and the arithmetic bought nothing: ADD KEY PAIR already refuses
-- to overwrite a name ("Key-pair 'DLT_DEV_KEY_1' already exists"). So the guard
-- is the server's own uniqueness check, and a duplicate is a no-op.
--
-- Rotating on purpose is therefore explicit, never a side effect of a re-run:
--   ALTER USER dlt_dev ROTATE KEY PAIR DLT_DEV_KEY_1 PUBLIC_KEY = '<new key>';
EXECUTE IMMEDIATE $$
BEGIN
  IF (LENGTH('{{ DLT_DEV_PUBLIC_KEY }}') < 100) THEN
    RETURN 'STOP: DLT_DEV_PUBLIC_KEY parameter missing or too short';
  END IF;

  ALTER USER dlt_dev ADD KEY PAIR DLT_DEV_KEY_1
    PUBLIC_KEY = '{{ DLT_DEV_PUBLIC_KEY }}';
EXCEPTION
  WHEN OTHER THEN
    IF (SQLERRM LIKE '%already exists%') THEN
      RETURN 'KEY UNCHANGED: DLT_DEV_KEY_1 already registered';
    ELSE
      RAISE;
    END IF;
END;
$$;

-- =============================================================================
-- 6. POST-CONDITIONS (cheap assertions, they change nothing)
--    Run in SYSADMIN, which can see the database/warehouse it owns; role and
--    user are checked in USERADMIN (ACCOUNTADMIN cannot see either on this
--    account, so asserting from there would produce a false FAIL).
-- =============================================================================
USE ROLE SYSADMIN;

SHOW WAREHOUSES LIKE 'COMPUTE_WH';
SELECT 'postcheck' AS phase, 'warehouse COMPUTE_WH exists' AS target,
       IFF(COUNT(*) = 1, 'OK', 'FAIL') AS verdict
  FROM TABLE(RESULT_SCAN(LAST_QUERY_ID(-1)))
 WHERE "name" = 'COMPUTE_WH';

SHOW DATABASES LIKE 'github_raw';
SELECT 'postcheck' AS phase, 'database github_raw exists, owned by SYSADMIN' AS target,
       IFF(COUNT(*) = 1, 'OK', 'FAIL') AS verdict
  FROM TABLE(RESULT_SCAN(LAST_QUERY_ID(-1)))
 WHERE "name" = 'GITHUB_RAW' AND "owner" = 'SYSADMIN';

USE ROLE USERADMIN;

-- SHOW is immediate for these objects too: INFORMATION_SCHEMA would need a
-- current database, ACCOUNT_USAGE lags. These assertions must not lie.
SHOW ROLES LIKE 'data_engineer';
SELECT 'postcheck' AS phase, 'role data_engineer exists, owned by USERADMIN' AS target,
       IFF(COUNT(*) = 1, 'OK', 'FAIL') AS verdict
  FROM TABLE(RESULT_SCAN(LAST_QUERY_ID(-1)))
 WHERE "name" = 'DATA_ENGINEER' AND "owner" = 'USERADMIN';

SHOW USERS LIKE 'dlt_dev';
SELECT 'postcheck' AS phase, 'user dlt_dev is TYPE=SERVICE with role data_engineer' AS target,
       IFF(COUNT(*) = 1, 'OK', 'FAIL') AS verdict
  FROM TABLE(RESULT_SCAN(LAST_QUERY_ID(-1)))
 WHERE "name" = 'DLT_DEV' AND "type" = 'SERVICE' AND "default_role" = 'DATA_ENGINEER';

-- The registered public key, read straight from the user object.
-- Expected: RSA_PUBLIC_KEY_FP = SHA256:<the fingerprint printed at key creation>.
DESC USER dlt_dev;

-- =============================================================================
-- 7. ROLLBACK (manual, NOT executed) — reverse order of creation.
--    Documented here so the teardown is never improvised.
--
--    USE ROLE ACCOUNTADMIN;
--    ALTER USER dlt_dev REMOVE KEY PAIR DLT_DEV_KEY_1;   -- destroy the credential
--    DROP USER IF EXISTS dlt_dev;                        -- revoke every grant
--    DROP ROLE IF EXISTS data_engineer;                  -- now safe: no grantees
--    DROP DATABASE IF EXISTS github_raw;                 -- ⚠ deletes all raw data
--    DROP WAREHOUSE IF EXISTS COMPUTE_WH;                -- ⚠ stop billing forever
--    rm -rf ~/.snowflake/keys/github_raw/dlt_dev         -- private key (outside git)
-- =============================================================================



