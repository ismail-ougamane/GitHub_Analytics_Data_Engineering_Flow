# Architecture diagrams

The SVGs embedded in the root `README.md` come from the `.excalidraw` scenes
next to them:

| Source (canonical) | Rendered (embedded in README) |
|--------------------|-------------------------------|
| `infra.excalidraw` | `infra.svg` — what runs where |
| `pipeline-flow.excalidraw` | `pipeline-flow.svg` — one run of the DAG |
| `snowflake.excalidraw` | `snowflake.svg` — schemas, roles, compute |
| `dbt-lineage.excalidraw` | `dbt-lineage.svg` — dbt model lineage |

**GitHub renders only the SVG** — an `.excalidraw` file is a JSON scene, so it
shows up as plain text. That is why every diagram is committed twice: the
source for editing, the export for reading. Never commit one without the other.

## Editing a diagram

1. Open the `.excalidraw` file on [excalidraw.com](https://excalidraw.com)
   (File → Open) or with the VS Code Excalidraw extension.
2. Edit, then export: Menu → *Export image* → **SVG**, background on, no
   "embed scene".
3. Overwrite the matching `.svg` and commit both files in the same PR.

## Automated export (used by ticket-004)

The `excalidraw-to-svg` npm CLI is broken for this scene set: it runs
`@excalidraw/utils` inside jsdom, which has no canvas (`getContext` is not
implemented) — the same failure happens even with `@excalidraw/utils` pinned
to 0.1.2. Ticket-004 therefore exported through a small `puppeteer-core`
script driving the installed Chrome, loading the `@excalidraw/utils@0.1.2`
UMD bundle in a real browser and calling `ExcalidrawUtils.exportToSvg`.

The exact script and run log are preserved in
[docs/tickets/TICKET-004-readme-architecture-diagram.md](../tickets/TICKET-004-readme-architecture-diagram.md).