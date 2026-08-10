# BC-CAJA-PILOT-001 — Summary

Verdict: `BC CAJA MVP — READY FOR OPTICA PILOT`.

The canonical standalone launcher is `BC-Caja.exe` inside the packaged `BC-Caja` folder. It does not require VS Code, Python, PYTHONPATH, the source repository, Internet access, or a specific current working directory.

Production data remains external at `%LOCALAPPDATA%\BC\Caja`:

- `bc_caja.sqlite3`
- `Backups/`
- `Logs/`

Updating the application folder does not overwrite the database. The application folder and data folder are separate by construction.

Final BC Caja regression: 52 tests plus 4 subtests passed. Packaged first-run, close, backup, restart and recovery passed on temporary storage.
