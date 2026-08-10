# Test evidence

- `python -m pytest tests/caja_diaria -q`
- Result: `53 passed, 4 subtests passed`.
- UI contract order: PASS.
- Source GUI construction smoke: alive after 6 seconds, no startup error log.
- Extracted ZIP first-run: exit 0.
- Packaged migration 003: present.
- Packaged backup: created.
- Forbidden package entries: 0.