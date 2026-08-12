# BC-CAJA-UX-006 — High-fidelity correction

- Mission: BC-CAJA-UX-006
- State: VISUAL IMPLEMENTATION VERIFIED
- Base: 1850d0fcc58618547a315b1a84bbe47bb70d156d
- Working HEAD: afa3371ad9f70a5a9679a2ab03db338b40b6d257
- Real entrypoint: bc_caja.main([])
- Final capture: entrypoint-final-1366x768.png
- Final capture SHA-256: c7d4ab76600262e7bda0aa9345e727282de5d0e31467666f6ba8ad14d36b977d
- Synthetic populated-state capture: layout-final-1366x768.png
- Populated-state SHA-256: 06cc7c9f877d25f9f7f1dd0936553ffdac20a17341f4d9fcdb02431ac8e1fd23

The principal screen now follows the canonical two-column composition: clean header/navigation, seven KPI cards, five-section form, movement toolbar/table/pagination, and horizontal cash-count formula. Operational behavior remains delegated to the existing controller/domain/SQLite stack.

## Layout overlap correction

The real 1366x768 entrypoint now uses bounded left/right columns with a 16 px gutter, two contained action rows, a 12 px separation before the compact bottom cash-count strip, and separated header/KPI bands. No domain or persistence behavior changed.
