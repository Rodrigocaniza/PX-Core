PASS
Baseline origin/main 098a9fbd95549cd4308a4754b69f90aa93eb6fca (BC Caja 1.0.0-rc.14)
Baseline verificada antes de tocar nada 225 pruebas + 4 subpruebas
Fuentes verificadas 12 sha256 ok
Evidencia visual 3 sha256 ok (grilla 1920x1080 y 1366x768, dialogo Corregir estado)
Evidencia visual fail-closed: la captura aborta si el contrato no se cumple
Port sin merge: 3 archivos byte a byte desde 41ee4ce, hash identico al MANIFEST del slice viejo
  modulos/caja_diaria/domain/models.py bec3663c60d42fb76d9776b46a411e99843689ef9cde3f2b21b011a5aecf0e54
  modulos/caja_diaria/application/ports.py b8da9ec7a587d829c482fa0b7aa687e31366a1e56b077d8e00ec42b639c0ea60
  modulos/caja_diaria/infrastructure/sqlite_repository.py 030b098dea6a64a3c4ed174c0816a88da157bccec575753314258b48253f5c75
Migraciones 15 latest 015_admin_counts_notifications.sql (sin cambios de esquema)
Pruebas 243 + 4 subpruebas (225 baseline + 18 nuevas)
ZIP no aplica: empaquetado bloqueado por HUMAN_GATE-PEDIDOS-002
EXE no aplica: empaquetado bloqueado por HUMAN_GATE-PEDIDOS-002
Reglas economicas de Caja sin cambios
Cambios canonicos posteriores a rc.11 preservados: arqueo, administrador, correo de cierre, mail ops, outbox, Gestion Central
Laboratorio en la grilla fuera de alcance: requiere join contra sale_items
HUMAN_GATE viejo RC12-PEDIDOS-001 anulado, no heredado
Rama y worktree de BC-CAJA-APERTURA-CAJA-001 sin tocar
