# Ticket 003 — Run Airflow locally with the Astro CLI

**Status:** in review · **Owner:** ismail-ougamane · **Date:** 2026-11-10

> As a data engineer, I want a local Airflow so that I can develop and test DAGs.

## Acceptance criteria

| ID | Criterion | Proof |
|----|-----------|-------|
| AC-1 | `astro dev start` brings up Airflow | `cd orchestration && astro dev start` → 4 running containers (`astro dev ps`); `astro dev run dags list` lists `example_astronauts` |
| AC-2 | The Airflow UI opens on <http://localhost:8080> | `curl -sS -o /dev/null -w '%{http_code}' http://localhost:8080/` → `200` |
| AC-3 | The example DAG and its tests in `tests/dags` pass | `cd orchestration && astro dev pytest tests/dags` → `3 passed` + `✔ All tests passed!` |

## Plan (decisions D1–D8)

- **D1** The Astro project lives in `orchestration/`, not the repo root — one
  folder "specific for airflow", small Docker build context, and the Airflow
  lifecycle stays out of the ingestion/analytics layout. All `astro` commands
  run from that directory (`astro dev start`, `astro dev pytest tests/dags`).
- **D2** Scaffolded with `astro dev init` (Astro CLI 1.47.0) in a temp
  directory and copied in — never `--force` over the repo, so `README.md`,
  `.gitignore` and `docs/` could not be clobbered.
- **D3** The generated `Dockerfile` pins the runtime:
  `astrocrpublic.azurecr.io/runtime:3.3-12` = Airflow 3.3.2+astro.3, Python
  3.14. `astro dev pytest` requires Runtime 3.1.1+ — satisfied.
- **D4** CLI 1.47 ships the example DAG and its test at exactly the AC paths:
  `dags/exampledag.py` (`example_astronauts`, TaskFlow API) and
  `tests/dags/test_dag_example.py` (DagBag: no import errors, every DAG has
  tags and retries). Both shipped unmodified — Airflow-3-native
  (`from airflow.sdk import dag, task`).
- **D5** `.astro/config.yaml` (project name) **is committed**: Astro's project
  detection needs it; only `.astro/standalone/`, `.astro/worktrees/`,
  `.astro/*.local.*` are gitignored — matching the template's own `.gitignore`.
- **D6** `requirements.txt` / `packages.txt` stay comment-only/empty: Runtime
  3.x already ships `pytest`, `requests` and the pre-installed providers.
- **D7** `airflow_settings.yaml` is committed as a **placeholder only** (local
  connections/variables). Secrets policy unchanged: real credentials go into
  `.env` (gitignored) or a secrets backend — never into the settings file.
- **D8** Local toolchain (macOS): `brew tap astronomer/tap && brew install
  astronomer/tap/astro --without-podman` (keeps Docker Desktop instead of
  pulling in Podman). Docker CLI + credential helpers symlinked into
  `/opt/homebrew/bin` because the old `/usr/local/bin/docker` symlink pointed
  at the deleted `/Volumes/Docker`.

## TDD log

- [x] **RED** — before the project existed: `astro dev parse` → *"this is not
  an Astro project directory"*; first `astro dev pytest tests/dags` → *"Failed
  to find a container runtime"* (docker CLI off `PATH`) → fixed via D8
  symlinks, then the "not an Astro project" RED stands on its own.
- [x] **GREEN (parse)** — `astro dev parse` →
  `1 passed … ✔ No errors detected in your Dags`.
- [x] **GREEN (AC-3)** — `astro dev pytest tests/dags -a "-v"`:
  `test_file_imports`, `test_dag_tags`, `test_dag_retries` →
  `3 passed … ✔ All tests passed!` (Astro Runtime 3.3-12, Python 3.14.10,
  pytest 9.2.0). Re-ran with the environment running: `3 passed` again.
- [x] **GREEN (AC-1)** — `astro dev start --no-browser` → `astro dev ps`:
  scheduler, dag-processor, api-server (`:8080`), triggerer `running`,
  postgres `running`, db-migration `exited` (one-shot);
  `astro dev run dags list` → `example_astronauts | dags/exampledag.py`.
- [x] **GREEN (AC-2)** — `curl http://localhost:8080/` → `200`,
  `/home` → `200`, `/api/v2/version` → `{"version":"3.3.2+astro.3"}`.

## Verification matrix (2026-11-10)

| ID | Criterion | Result | Evidence |
|----|-----------|--------|----------|
| AC-1 | `astro dev start` brings up Airflow | ✅ pass | `astro dev ps` 4 components running; `astro dev run dags list` shows `example_astronauts` |
| AC-2 | UI on <http://localhost:8080> | ✅ pass | `http_code=200`; Airflow API `3.3.2+astro.3` |
| AC-3 | Example DAG + `tests/dags` pass | ✅ pass | `3 passed, ✔ All tests passed!` (offline and with the env up) |

Note: Astro CLI 1.47 additionally serves the UI through a project-scoped
reverse proxy at `http://orchestration.localhost:6563` (also `200`). The AC
port `8080` is the api-server's direct mapping, so both work with zero
configuration.

## Changelog

### 2026-11-10
- Added `orchestration/` Astro project (CLI 1.47.0 scaffold, Runtime
  `3.3-12`): `Dockerfile`, `.dockerignore`, `requirements.txt`,
  `packages.txt`, `airflow_settings.yaml`, `dags/exampledag.py` +
  `dags/.airflowignore`, `tests/dags/test_dag_example.py`, `.astro/config.yaml`,
  `include/.gitkeep`, `plugins/.gitkeep`.
- `.gitignore`: added the Astro section (`.astro/standalone/`,
  `.astro/worktrees/`, `.astro/*.local.*`, `logs/`, `.env`).
- `README.md`: added the "Run Airflow locally" section (install, everyday
  loop, UI URL, tests, local-only files).
- Proved AC-1/AC-2/AC-3 live on this machine (verification matrix above);
  recorded the RED state and the two toolchain fixes (docker symlinks,
  `--without-podman` install) as TDD/repro notes.
- Left the environment running for manual UI review; `astro dev stop` shuts
  it down.
