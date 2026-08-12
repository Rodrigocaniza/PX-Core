# BC-CAJA-UX-006 — Final operational and layout adjustment

- Mission: BC-CAJA-UX-006
- State: IMPLEMENTED_AND_VERIFIED — LOCAL_COMMIT_CREATED
- Base: 394a793b719b0e0d13f23eefff3fbd9d71b3dc9c
- Real entrypoint: bc_caja.main([])
- Final capture: final-1366x768.png
- Data in capture: synthetic/demo only

## Delivered

The daily screen now calculates pending balance from Total minus Cash, Card/Cheque and Transfer, clamped to zero. It displays a passive Estado: ABIERTA/CERRADA badge, provides a dedicated expense dialog requiring only concept and amount, identifies expenses in movements, and delegates closed-day protection and cash-only expense subtraction to the existing domain.

The lower Resumen para arqueo was removed only from Caja diaria; the Arqueo tab remains. The form grew from 356 to 400 px and the movement grid from 310 to 354 px, preserving wheel/scrollbar behavior and the two-column high-fidelity composition.

## Validation

Real 1366x768 entrypoint with 30 synthetic sales plus one synthetic expense: PASS. Sale case 1.500.000 + 250.000 = 1.750.000, payments 1.000.000 + 500.000 + 0, pending 250.000: PASS. Closed-day expense rejection: PASS. Full regression: 72 passed + 4 subtests passed.