PASS
RC BC Caja 1.0.0-rc.15 mision BC-CAJA-RC15-APERTURA-PEDIDOS-001
Baseline origin/main 098a9fbd95549cd4308a4754b69f90aa93eb6fca (rc.14)
Integra BC-CAJA-APERTURA-CAJA-001 (gate PASS) y BC-CAJA-PEDIDOS-ATENCION-002 (gate PASS)
Conflicto real unico .bc-command-center/verification.json resuelto conservando ambas entradas
CajaDiaria.py auto-merge limpio: zonas distintas (cabecera vs pestana Pedidos)
Fuentes verificadas 13 sha256 ok
Evidencia visual 9 sha256 ok (apertura, consulta, pedidos, contraste de acciones, dialogo; 1920x1080 y 1366x768)
Evidencia visual fail-closed: las capturas abortan si el contrato no se cumple
Pruebas 258 + 4 subpruebas (225 baseline + 10 Apertura + 18 Pedidos + 5 contraste de acciones)
Correccion UX: acciones disponibles solidas, no disponibles gris apagado con motivo al pasar el mouse
Contraste verificado en tiempo de ejecucion pedido por pedido: salto de luminancia minimo 0.30
Focalizados Apertura 13, focalizados Pedidos 21, adyacente 31
Migraciones 15 latest 015_admin_counts_notifications.sql (sin cambios respecto de rc.14)
ZIP releases/BC-CAJA-1.0.0-rc.15-win64.zip 24149757 bytes
zip_sha256 167b170974483839542355926538bc7395188ca22eb654d51f89a620a328127d
EXE dist/BC-Caja/BC-Caja.exe 6609127 bytes
exe_sha256 86cc895da7530eadc8852f0523cc6dd2de00346e3a6ba6275b3b13be8ef6d006
Preflight canonico PASS y clon productivo PASS (rc.11 -> rc.15 sobre copia de la base real)
Smoke del binario: arranca y aplica las 15 migraciones sobre base temporal
Backup previo bc-caja-pre-1.0.0-rc.15-20260817-161651-884812.sqlite3 sha256 identico al original
Rollback documentado y ejecutable ver ROLLBACK.md
Reglas economicas de Caja sin cambios
Arqueo, Administrador, correo de cierre y mail ops preservados y en verde
INSTALL_GATE-RC15-001 resuelto: opcion A, promover rc.11 -> rc.15 con preflight exhaustivo
INSTALACION REALIZADA transaccional: backup preinstall verificado, rc.11 preservada en BC-Caja-Pilot.previous-rc11
Migracion 015 aplicada por el flujo soportado, sin SQL manual
Post-install sobre la base productiva: 15 migraciones, integridad ok, filas y montos identicos
exe instalado en disco sha256 identico al construido
HUMAN_GATE-RC15-INSTALADA-001 PASS sobre la instalacion real, ver GATE_VERDICT.md
Rollback vigente mientras se conserven el backup preinstall y BC-Caja-Pilot.previous-rc11
main sin tocar sin force-push: el fast-forward queda como accion explicita autorizada por el usuario
