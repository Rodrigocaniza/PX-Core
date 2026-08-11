# BC-CAJA-TIME-001 — Summary

Implemented from canonical `origin/main` at merge commit
`e0e0c7f2b9a7cecf3d3a27d0cae5dff8b4efa7e4` in isolated branch
`agent/bc-caja-time-001`.

## Delivered

- Automatic real opening and closing timestamps.
- Persisted session duration in seconds.
- Monday–Friday overtime trigger strictly after 18:10.
- Saturday overtime trigger strictly after 12:10.
- Confirmed minimum of 60 overtime minutes when triggered.
- Closure dialog shows opening, closing, duration and overtime result.
- SQLite migration `004` preserves existing databases and productive data.

## Explicit pending business policy

No accumulation or rounding rule beyond the confirmed first hour was
implemented. Sunday overtime policy also remains undefined and is persisted as
`NULL`, never silently interpreted as zero.

## Scope protection

UX-004, legacy calculations, workbook import, backups, restart recovery and
external productive-data paths remain unchanged. No BC-Core, BC-Inventario or
original dirty-worktree file was touched.
