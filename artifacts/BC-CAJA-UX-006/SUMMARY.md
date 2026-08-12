# BC-CAJA-UX-006 — Integrated expenses and real cash count

- Mission: BC-CAJA-UX-006
- State: IMPLEMENTED_AND_VERIFIED — LOCAL_COMMIT_CREATED
- Base: 9a01037281db580af713f059283d90b58af6dfd1
- Real entrypoint: bc_caja.main([])
- Final capture: final-1366x768.png
- Capture data: synthetic/demo only

## Delivered

Caja diaria now contains compact section 6 Gastos with only required Description and Amount plus its own Guardar gasto action. The former separate Registrar gasto action and modal were removed. Amount uses Paraguayan dot formatting; the existing controller/domain persist the expense, identify it in movements, update the Gastos KPI and subtract it only from expected cash. Closed boxes disable this section.

Arqueo now presents the system expected cash, denomination quantities and live subtotals, physical counted cash, signed difference and a clear conforming/difference alert. Differences never block saving. Existing CashCount persistence stores date/day link, branch, expected, counted, difference, status, denomination detail and timestamp.

## Validation

Real 1366x768 entrypoint: integrated Ferretería expense 200.000 PASS; 32 movement rows and scroll PASS. Expected 1.500.000 with conforming count 1.500.000, shortage 1.450.000 (-50.000), and surplus 1.550.000 (+50.000): visible and saved PASS. Full regression: 75 passed + 4 subtests passed.