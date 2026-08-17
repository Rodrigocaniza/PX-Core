PASS
Mision BC-CAJA-PEDIDOS-OPERATIVOS-RC30-001 sobre origin/main 291fe40 (BC Caja 1.0.0-rc.30)
Fuentes verificadas 6 sha256 ok
Evidencia visual 5 sha256 ok (Pedidos 1920x1080 y 1366x768, alerta RC28, Seguimiento RC27)
Evidencia visual fail-closed: el smoke aborta si el contrato no se cumple
Pruebas 682 + 4 subpruebas (669 baseline + 13 nuevas)
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
