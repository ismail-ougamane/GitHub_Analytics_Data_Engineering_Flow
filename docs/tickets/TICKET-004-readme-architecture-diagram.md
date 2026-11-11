# Ticket 004 — README starts with the architecture diagram

**Status:** in review · **Owner:** ismail-ougamane · **Date:** 2026-11-11

> As a new team member, I want a README with diagrams so that I understand the
> project quickly.

## Acceptance criteria

| ID | Criterion | Proof |
|----|-----------|-------|
| AC-1 | README describes the goal: GitHub API → dlt → Snowflake → dbt → dashboards, orchestrated by Airflow | `README.md` opening paragraph + "What one run looks like" table |
| AC-2 | An Excalidraw architecture diagram renders on GitHub | `docs/architecture/architecture-flow.svg` embedded at the top of `README.md`; visual proof: PNG rasterised from the SVG + screenshot of the rendered README on github.com |
| AC-3 | The README explains the *why* of every choice | "Why these choices" table (GitHub GraphQL, dlt, Snowflake ELT, dbt, charts-in-dbt, Airflow on Astro — each with rejected alternatives) |

## Plan (decisions D1–D9)

- **D1** Branch off `origin/main` (`docs/ticket-004-readme-architecture`), not
  off `feat/ticket-003-*`: ticket-003 is still in review and ticket-004 must
  not smuggle its changes into the same PR. New content is inserted *above*
  the existing sections; the two tickets touch different regions, so no
  conflict is expected at merge time.
- **D2** Diagrams are **Excalidraw, not Mermaid** (user decision). Layout:
  `.excalidraw` source (canonical, editable) **plus** a rendered `.svg` per
  diagram, both committed — GitHub renders only the SVG (an `.excalidraw`
  scene is JSON text; an `excalidraw.com/#json=…` link is just a link).
- **D3** Scenes are generated from a throwaway Node script (not committed) to
  keep geometry deterministic: diagram 1 = end-to-end flow (source → dlt →
  Snowflake RAW/STAGING/MARTS → dbt charts, with a dashed Airflow band
  underneath); diagram 2 = dbt lineage (RAW sources → `stg_github__*` →
  `fct_*`/`dim_*` → charts). Fonts: `fontFamily: 2` (Helvetica — resolves
  everywhere) for prose, `fontFamily: 3` (Cascadia) for model names; free
  (unbound) texts and arrows so nothing depends on renderer-side measurement.
- **D4** The third planned diagram (Airflow task sequence) is dropped in
  favour of a markdown table — "What one run looks like" — cheaper to keep
  correct than a third drawing.
- **D5** The README states the diagrams are the **target** architecture and
  carries a "What exists today" status table, so a new teammate cannot mistake
  the plan for a running pipeline (ingestion/dbt/charts do not exist yet;
  `orchestration/` arrives with ticket-003).
- **D6** `docs/architecture/README.md` documents the two-files-per-diagram
  contract (never commit one without the other), the manual export workflow,
  and why the automated npm path failed.
- **D7** `.gitattributes` marks `*.excalidraw` as JSON for syntax highlighting.
- **D8** `docs/tickets/README.md` gets one index row for ticket 004 (ticket
  003's row lands with its own PR — its branch is ahead of this one).
- **D9** An unrelated uncommitted revert of `TICKET-001-*.md` was found in the
  working tree before checkout; it was stashed (`stash@{0}`, labelled) and is
  **not** part of this ticket. Files are staged by explicit path only.

## TDD / verification log

- [x] **Structural (RED→GREEN)** — generator asserts every element carries the
  required Excalidraw keys, ids are unique, arrows have ≥ 2 points:
  `architecture-flow: 36 elements OK`, `dbt-lineage: 51 elements OK`.
- [x] **Export attempt 1 (RED)** — `npx -y excalidraw-to-svg@3.1.0 …` fails:
  the CLI reads `./node_modules/@excalidraw/utils/dist/excalidraw-utils.min.js`
  **relative to CWD** (only works from an install root).
- [x] **Export attempt 2 (RED)** — run from an install root with default
  `@excalidraw/utils` (0.1.8): dist layout changed (`dist/prod/index.js`), no
  `excalidraw-utils.min.js`. Pinned `@excalidraw/utils@0.1.2` → file exists.
- [x] **Export attempt 3 (RED)** — jsdom has no `HTMLCanvasElement.getContext`
  ("Not implemented… without installing the canvas npm package"); the
  `canvas-5-polyfill` does not save it → "svg was not created".
- [x] **Export attempt 4 (GREEN)** — `puppeteer-core` + installed Chrome
  (`/Applications/Google Chrome.app`), page loads the `@excalidraw/utils@0.1.2`
  UMD bundle and calls `ExcalidrawUtils.exportToSvg({elements, appState,
  files})`: `architecture-flow.svg` 17 327 bytes, `dbt-lineage.svg`
  26 425 bytes — both `<svg … viewBox=…` with all text nodes.
- [x] **Visual (AC-2)** — SVGs rasterised with headless Chrome
  (`--headless --screenshot --window-size=1660,800 / 1500,620`) and inspected:
  boxes, arrows, colours, legend and labels all legible; no text overflow.
- [x] **AC assertions** — README contains both `![…](docs/architecture/*.svg)`
  embeds; goal chain "GitHub GraphQL API → dlt → Snowflake → dbt → dbt charts"
  in the opening paragraph; "Why these choices" table has one row per stage
  plus the orchestrator; "What exists today" table present.
- [x] **Scope check** — `git status --short` lists only the files of this
  ticket; `stash@{0}` still holds the unrelated TICKET-001 leftover.

## Verification matrix (2026-11-11)

| ID | Criterion | Result | Evidence |
|----|-----------|--------|----------|
| AC-1 | Goal chain stated in README | ✅ pass | opening paragraph + task table |
| AC-2 | Excalidraw diagram renders on GitHub | ✅ pass | SVG committed + rasterised PNG inspected; screenshot of `github.com/…/blob/docs/ticket-004-readme-architecture/README.md` shows **both** SVGs rendering on GitHub |
| AC-3 | Rationale per choice | ✅ pass | "Why these choices" table, 6 rows |

## Changelog

### 2026-11-11
- `README.md`: architecture section now opens the README (goal chain, embedded
  `architecture-flow.svg`, task-sequence table, embedded `dbt-lineage.svg`,
  "Why these choices" table, "What exists today" status, repository map,
  diagram-editing instructions). Existing sections untouched.
- `docs/architecture/`: added both `.excalidraw` sources and both `.svg`
  renders, plus a README documenting the two-files-per-diagram contract and
  the export tooling saga.
- `.gitattributes`: `*.excalidraw linguist-language=JSON`.
- `docs/tickets/README.md`: index row for ticket 004.
- Noted the jsdom-based `excalidraw-to-svg` failure and the working
  puppeteer-core + Chrome export path (TDD log above).
- Opened draft PR [#6](https://github.com/ismail-ougamane/GitHub_Analytics_Data_Engineering_Flow/pull/6);
  first on-GitHub render check exposed a real exporter bug: multi-line free
  text collapses (utils 0.1.2) — sub-labels re-generated as **one single-line
  text element per line**, both SVGs re-rendered, re-verified locally and
  re-verified on github.com; PR flipped to ready afterwards.