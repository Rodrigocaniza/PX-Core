# Test and package evidence

- Full BC Caja suite: 57/57 PASS.
- Operation E2E covers create, edit, logical void, close, history, backup and restart: PASS.
- GUI smoke at 1366x768: PASS.
- Extracted EXE first-run: exit 0.
- External SQLite created: yes.
- External backup count: 1.
- ZIP entries: 1,057.
- Forbidden package entries: 0.
- ZIP SHA-256: `52F29A087BE19C653294A6AD8C6868D1FCF60DAA7C87557D44B43C3897F176F9`.
- EXE SHA-256: `9411EBF7A087A68AD7D61357893B4DDA8B53EA61CAF3966AE28E02D263F51AFD`.
- Productive data remains outside the package at `%LOCALAPPDATA%\BC\Caja`.
