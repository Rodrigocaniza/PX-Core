# BC-CAJA-PILOT-001 — Local pilot + deployment

Objective: produce a Windows-installable BC Caja build, rehearse the complete daily cycle, and deploy reversibly to one optical-store workstation.

Scope:

1. Freeze the Safe Closure commit and entry point.
2. Package without developer tooling.
3. Configure `%LOCALAPPDATA%/BC/Caja` and backup retention.
4. Rehearse open, entry/import, edit/void, totals, count, close, restart, backup and restore.
5. Record operator acceptance and rollback instructions.
6. Observe the first live operational close.

Exclusions: BC Gestión, cloud, Telegram, analytics, multi-user and UI redesign.

Exit: installable build launches after restart; rehearsal and restore pass; operator completes the runbook; first live day reconciles with recoverable backup. Target: `BC CAJA MVP — OPERATIVO EN ÓPTICA`.
