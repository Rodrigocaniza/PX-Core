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
