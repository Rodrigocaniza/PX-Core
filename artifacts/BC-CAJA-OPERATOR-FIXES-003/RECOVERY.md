# Recovery / Auto-Resume

Canonical branch: `feature/caja-operator-fixes-003`.

1. `git fetch origin feature/caja-operator-fixes-003`
2. `git switch feature/caja-operator-fixes-003`
3. Reset to `origin/feature/caja-operator-fixes-003` only from a clean checkout when exact remote recovery is intended.
4. `py -m pytest tests/caja_diaria -q`
5. `py tools/validate_bc_caja_window_lifecycle.py`
6. `py bc_caja.py --self-check`
7. Confirm `.bc-command-center/verification.json` maps this mission to `bc-caja-operator-fixes`.

Migrations `010` and `011` run automatically when the repository opens. `010` adds `agreement_amount`. `011` copies every changed `balance_text` into `agreement_balance_corrections` before normalization. To investigate or recover an affected value, query `agreement_balance_corrections(entry_id, previous_balance_text, corrected_balance_text, corrected_at)`; do not overwrite the database manually. Restore from the pre-operation backup if database-level rollback is required.

After verification, resume planning from repository artifacts and current remote HEAD, not chat reconstruction.

Canonical continuation after closure: fetch the remote branch, verify its HEAD and restart planning from the repository roadmap plus closed mission artifacts. Do not replay the implementation mission.
