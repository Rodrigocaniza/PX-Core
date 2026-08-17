PASS
RC BC Caja 1.0.0-rc.15 mision BC-CAJA-RC15-APERTURA-PEDIDOS-001
Baseline origin/main 098a9fbd95549cd4308a4754b69f90aa93eb6fca (rc.14)
Integra BC-CAJA-APERTURA-CAJA-001 (gate PASS) y BC-CAJA-PEDIDOS-ATENCION-002 (gate PASS)
Conflicto real unico .bc-command-center/verification.json resuelto conservando ambas entradas
CajaDiaria.py auto-merge limpio: zonas distintas (cabecera vs pestana Pedidos)
Fuentes verificadas 13 sha256 ok
Evidencia visual 7 sha256 ok (apertura, consulta, pedidos, dialogo; 1920x1080 y 1366x768)
Evidencia visual fail-closed: las capturas abortan si el contrato no se cumple
Pruebas 253 + 4 subpruebas (225 baseline + 10 Apertura + 18 Pedidos)
Focalizados Apertura 13, focalizados Pedidos 21, adyacente 31
Migraciones 15 latest 015_admin_counts_notifications.sql (sin cambios respecto de rc.14)
ZIP releases/BC-CAJA-1.0.0-rc.15-win64.zip 24148167 bytes
zip_sha256 c82f89b9461faf7a6f15bc36a7df46653565d21cdb56271a404f97b796618aef
EXE dist/BC-Caja/BC-Caja.exe 6606940 bytes
exe_sha256 44bf7225f0edc2befcf57ba37b5faed47ceee62c73b1518c2f611775b316b80d
Smoke del binario: arranca y aplica las 15 migraciones sobre base temporal
Backup previo bc-caja-pre-1.0.0-rc.15-20260817-161651-884812.sqlite3 sha256 identico al original
Rollback documentado y ejecutable ver ROLLBACK.md
Reglas economicas de Caja sin cambios
Arqueo, Administrador, correo de cierre y mail ops preservados y en verde
INSTALACION NO REALIZADA bloqueada por INSTALL_GATE-RC15-001
Version instalada real en la PC 1.0.0-rc.11: rc.12, rc.13 y rc.14 nunca se instalaron
main sin tocar sin force-push
