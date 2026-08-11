# Safe Closure Evidence — BC-CAJA-UX-002

Verdict: PASS.

Safe Closure was performed from a temporary isolated PX-Core worktree because
the operational worktree contained four pre-existing changes outside the
BC-CAJA-UX-002 scope. Those files were not modified, discarded, reset,
stashed, committed or attributed to BC Caja.

## Isolated worktree baseline

- Materialized from `origin/feature/caja-diaria` at
  `5ed42aef6994bcbe491e8178c27bf5ded48c8414`.
- HEAD matched the remote feature branch: yes.
- Ahead/behind: `0/0`.
- Working tree before this evidence document: clean.
- UX-002 scope against `origin/main`: 11 files, all belonging to BC Caja,
  pilot packaging, tests or mission evidence.

## Final verification

- Previously completed functional suite: 55/55 PASS.
- Artifact Consistency from the isolated worktree: PASS.
- ZIP entries: 1,057.
- Forbidden package entries: 0.
- ZIP SHA-256:
  `03ECF69AB00271B0788C7778CE6AD85A624979360A20CFDE1C1950FAF7A1889B`.
- EXE SHA-256:
  `69629138AB29D7A30999E0C9DC6598741E7B3366E45E90C8C550AE5219C8D12C`.
- Package data remains external at `%LOCALAPPDATA%\BC\Caja`.

## Preserved operational worktree state

The following out-of-scope files were recorded before isolation and must
remain unchanged after worktree removal:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `Datos/movimientos.txt` | 47,737 | `EAC9CF6F2CA30F90F3AD5E4FD4C4839586ECC1156E00F519E5B493CAB97D0402` |
| `interfaz.py` | 379,756 | `18B3B23A2E6CC436B2DDE8D3E5AD960251A5B93A245E0CB5AC384585DFA705D9` |
| `main.py` | 2,758 | `4737D3498364EA1D8C77646A0D948C5DF67F0828451C6C0FCBA3BFD05D7BD542` |
| `GastosFijos.py` | 10,406 | `F530BB528C8D261F9A30F9E9F195D65F13EB824547584680D01A976237F3FDED` |
