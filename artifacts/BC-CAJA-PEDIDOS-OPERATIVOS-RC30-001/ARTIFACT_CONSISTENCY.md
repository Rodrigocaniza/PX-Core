PASS
Mision BC-CAJA-PEDIDOS-OPERATIVOS-RC30-001 sobre origin/main 291fe40 (BC Caja 1.0.0-rc.30)
Fuentes verificadas 6 sha256 ok
Evidencia visual 5 sha256 ok (Pedidos 1920x1080 y 1366x768, alerta RC28, Seguimiento RC27)
Evidencia visual fail-closed: el smoke aborta si el contrato no se cumple
Pruebas 682 + 4 subpruebas (669 baseline + 13 nuevas)

REVISION 2 (gate abierto desde equipo de desarrollo, sin tocar la Optica)
Convencion de hash declarada: fuentes con saltos normalizados a LF, evidencia visual en
  byte crudo. Antes cuatro fuentes estaban hasheadas en CRLF y dos en LF, asi que la
  verificacion daba mismatch fuera del equipo de origen. Contenido sin cambios
Punto 10 del gate resuelto: era defecto del harness, no del producto. El smoke navegaba
  con pestanas.set(Pedidos), que mueve el CTkTabview pero no repinta la barra de
  navegacion propia; la app oculta el segmented button (CajaDiaria.py:1017) y toda
  navegacion real pasa por seleccionar_pestana(), que mueve las dos mitades
Harness corregido: navega tocando el boton, y falla cerrado si Pedidos no queda resaltado
  o si otra pestana sigue encendida. Control negativo ejecutado: con la navegacion vieja
  aborta y no guarda captura. Codigo productivo sin tocar
Evidencia visual de Pedidos regenerada en 1920x1080 y 1366x768, con Pedidos resaltado
Focalizadas 13 + contrato visual UX004 3 = 16 passed
Suite completa 680 passed + 2 failed en tests/gestion_central/test_ui_interactions.py.
  Reproducidas identicas en el baseline 291fe40: deuda preexistente ajena a Caja,
  registrada como BC-GESTION-CENTRAL-UI-TIMING-FLAKE-001, no corregida aqui
Hallazgo adyacente NO corregido: CajaDiaria.py:3253 (editar desde Historial) usa
  pestanas.set directo y deja el resaltado en Historial. Preexistente en 291fe40, fuera
  del slice de Pedidos
BC-Core local desactualizado (recovery/command-center-safe-exit-ops-20260811, 7991df3) y
  sin Headless Executor. Sincronizar desde el origin/main canonico antes de la proxima
  mision de codigo que pretenda usarlo. No se mezclo con este gate

REVISION 3 (gate PASS y empaquetado de rc.31)
HUMAN_GATE-PEDIDOS-RC30-001 PASS generacion 2, 11/11, veredicto humano. Registrado en
  WORKFLOW.json y en GATE_VERDICT.md
Fuentes 7 sha256 ok (se suma pilot/package_docs/VERSION.txt), evidencia visual 5 sha256 ok
Suite 682 passed. Los 2 fallos de gestion_central de la corrida anterior pasaron en esta:
  confirmado que dependen del reloj. Siguen registrados como deuda separada, sin tocar
Version 1.0.0-rc.31 en VERSION_APLICACION y en pilot/package_docs/VERSION.txt, atada por
  prueba. Unico cambio de codigo desde el gate
Paquete releases/BC-CAJA-1.0.0-rc.31-win64.zip
  zip sha256 95e9148a2c712ccb6622f2fb89cc0dcc4e7547c002308ba532988217f95c2948
  exe sha256 62e8f1d87206b31b428892dc60266dde3394ef30a8b530b41f53563fe892152f
  21 migraciones embebidas, sin migracion nueva respecto de rc.30
Smoke del binario empaquetado en directorio de datos aislado: esquema en 021, integrity
  ok, foreign_key_check 0, outbox 0, sin startup-error.log
NO INSTALADO: este equipo no tiene rc.30. La instalacion vigente aca es de la serie rc.27
  y no existe backup preinstall ni rollback de rc.30. El destino productivo es la maquina
  de la Optica. Runbook en INSTALL_READINESS.md, reversion en ROLLBACK.md
Validacion post-install NO ejecutada y NO declarada
main 291fe40 sin tocar, sin force-push. Promocion pendiente hasta que rc.31 este instalada
  y validada en el destino real
Migraciones 21 sin agregar ninguna
Reglas economicas de Caja sin cambios
Autoridad del tronco preservada: estado anclado a la fila, alerta con filtro transportado, sucursal, Seguimiento y NextAction
Grilla de rc.15 NO resucitada: sin chips flotantes
Corregir estado con lista cerrada derivada de ORDER_TRANSITIONS, motivo obligatorio y auditoria en order_status_revisions
Contratos ajenos actualizados con su intencion preservada: operator_fixes_003, rc10, rc28, rc25
Funciones nuevas nombradas para no sombrear abrir_menu_mas de Seguimiento
Headless Executor NO DISPONIBLE en BC-Core: se siguio con el mecanismo actual, sin metricas inventadas
NO empaquetado y NO instalado: la RC vigente sigue siendo rc.30
main 291fe40 sin tocar, sin force-push

REVISION 4 (instalacion y validacion en la PC de la Optica, 18-08-2026)
Ejecutada desde el destino real. Canonical state verificado antes de tocar nada: repo,
  git-common-dir, fetch, origin/main 291fe40, HEAD de la rama, 20 worktrees, 0 leases
  vivos, gh autenticado como Rodrigocaniza, instalacion vigente rc.30 con su backup
  preinstall presente, 0 procesos BC-Caja, sin startup-error.log
Este equipo SI es el destino: tiene rc.30 y su backup. La serie de rollbacks local
  (previous-rc5..previous-rc15) difiere de la del equipo de casa (rollback-rc26-20260816h)
Artefacto recuperado del release privado, NO reconstruido: zip 34111433 bytes y
  sha256 95e9148a...c2948 ok, exe 62e8f1d8...2152f ok verificado en staging temporal ANTES
  de mover la instalacion vigente
Backup preinstall bc-caja-preinstall-1.0.0-rc.31-20260818-123848.sqlite3, hash verificado
  contra el original: identico
Rollback apartado y verificado: BC-Caja-Pilot.rollback-rc30-20260818-123848, VERSION rc.30,
  exe a38262a5 identico al original, 1136 archivos vs 1136. Ademas rc.30 quedo entera como
  .replaced-rc30-20260818-123848: dos copias independientes, no se borro nada
Instalacion transaccional por Move-Item + Move-Item: nunca hubo un estado con la
  instalacion borrada y la nueva sin poner. VERSION.txt instalado rc.31, exe 62e8f1d8 ok
Smoke sobre datos reales: Caja diaria, Pedidos, Seguimiento, Laboratorios e Historial.
  El punto 10 del gate verificado en produccion: al tocar Pedidos el resaltado de la barra
  de navegacion queda en Pedidos. Cierre limpio, 0 procesos residuales, sin startup-error.log
Validacion post-install: integrity_check ok, foreign_key_check 0, 21 migraciones sin
  agregar ni perder ninguna, DIFF de filas SIN CAMBIOS, DIFF de montos SIN CAMBIOS,
  mail_outbox 0. sha256 de la base productiva IDENTICO antes y despues: 1c4fcc40...98ec
Comprobacion aritmetica independiente: Historial Este mes da 2.220.000 + 3.350.000 mas una
  venta ANULADA de 830.000 = 6.400.000, exactamente el SUM(cash_entries.total) de la linea
  base. Datos reales enteros y la anulacion historica conservada como tal
Modal Configuracion inicial administrativa: aparece porque admin_users = 0, ya era asi bajo
  rc.30 segun la linea base. NO es regresion de rc.31. No se configuro credencial: es
  decision del dueno, no del instalador
Artifact Consistency reverificado en la Optica: 12 sha256 ok (7 fuentes en LF + 5 visuales
  en byte crudo), 0 mismatch
Suite completa reproducida en la Optica: 682 passed, 4 subtests, exit 0. Los 2 fallos de
  gestion_central no aparecieron: confirma una vez mas que dependen del reloj
Rollback NO necesario: rc.31 no escribio en la base durante el smoke
Promocion a main por fast-forward desde la rama de la mision, sin force-push
Evidencia nueva: INSTALL_EVIDENCE.md + 5 capturas install-rc31-*.png, hasheadas en el
  MANIFEST bajo install_evidence
