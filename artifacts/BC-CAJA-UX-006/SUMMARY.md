# BC-CAJA-UX-006 — High-fidelity correction

- Mission: BC-CAJA-UX-006
- State: VISUAL IMPLEMENTATION VERIFIED
- Base: 1850d0fcc58618547a315b1a84bbe47bb70d156d
- Working HEAD: afa3371ad9f70a5a9679a2ab03db338b40b6d257
- Real entrypoint: bc_caja.main([])
- Final capture: entrypoint-final-1366x768.png
- Final capture SHA-256: 9fabf28e61e5c8647463d4398cfe375c15470f67698b80114381cb012fb86bcb
- Synthetic populated-state capture: layout-final-1366x768.png
- Populated-state SHA-256: 94fed78545585b7cec7687347013fc640e120c8f06e7273d4ce1abb837c1dea5

The principal screen now follows the canonical two-column composition: clean header/navigation, seven KPI cards, five-section form, movement toolbar/table/pagination, and horizontal cash-count formula. Operational behavior remains delegated to the existing controller/domain/SQLite stack.

## Layout overlap correction

The real 1366x768 entrypoint now uses bounded left/right columns with a 16 px gutter, two contained action rows, a 12 px separation before the compact bottom cash-count strip, and separated header/KPI bands. No domain or persistence behavior changed.

## Final visible-behavior correction

Money entries format with dot thousands separators on focus loss; Total is recalculated only from frame plus lens prices; the main action strip contains Guardar venta, Limpiar and Registrar gasto only; the cash-count strip is compact; section 5 remains visible; and all seven KPI cards include aligned icons.

## Final layout correction before push

Effective entrypoint geometry with 30 synthetic rows: final section field bottom 627; primary action strip 715..741; compact cash-count strip begins at 759. Money formatting and derived total passed with 1.500.000 + 250.000 = 1.750.000. Treeview vertical scroll passed from yview (0.0, 0.3) to (0.16666666666666666, 0.4666666666666667). Observations persist through the existing source-reference metadata; no domain or schema change was made.
