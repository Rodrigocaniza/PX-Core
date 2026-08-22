# QA — PASS

- Focalizada: `22 passed in 1.12s`.
- Regresión no-GUI: `1389 passed, 37 skipped in 225.07s`.
- `compileall modulos/bc_sync`: PASS.
- `git diff --check`: PASS.
- Suite completa alcanzó 100%; 9 setups GUI preexistentes fallaron porque Python 3.13 del host no encuentra `init.tcl`. No guardan relación con Sync y no se alteraron.
- Se demostraron reinicio, offline, ACK perdido, retry, doble dirección, consolidación, nonce/revocación, conflictos y FactuFácil A–G.
