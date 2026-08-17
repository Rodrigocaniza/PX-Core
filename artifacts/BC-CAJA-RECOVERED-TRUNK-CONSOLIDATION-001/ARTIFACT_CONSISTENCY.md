PASS
RC BC Caja 1.0.0-rc.30 mision BC-CAJA-RECOVERED-TRUNK-CONSOLIDATION-001
Base tronco recuperado 491c363 (declaraba 1.0.0-rc.27, integra RC18 a RC29)
NO se partio de origin/main y NO se mergeo main completo
Portado de rc.15 solo Apertura automatica (0f10266) y contraste de acciones
Descartada a proposito la reescritura de la grilla de Pedidos de rc.15 (el tronco trae RC22/RC23/RC28, posteriores)
Seguimiento Pilar intacto: dominio y servicio de tracking sin cambios
Fuentes verificadas 7 sha256 ok
Evidencia visual 7 sha256 ok (apertura, consulta, seguimiento, recepcion, historial; 1920x1080 y 1366x768)
Pruebas 639 + 4 subpruebas (el tronco daba 616 con 2 archivos sin correr)
Contratos armonizados 5: rc4, ux004, ux006, rc26, rc15_ux_operativa, con la intencion preservada
Migraciones 21 latest 021_queda_a_confirmar.sql (sin migracion nueva)
fitz resuelto: dependencia de test, declarada en requirements-dev.txt, 0 archivos en dist/BC-Caja
ZIP releases/BC-CAJA-1.0.0-rc.30-win64.zip 25040083 bytes
zip_sha256 29b45e6b2877ae88a73dce1d55cab3d53e45077b5443c6a74788987b2b866afb
EXE dist/BC-Caja/BC-Caja.exe 7529443 bytes
exe_sha256 a38262a540ef59ea6be02ccb6a2db20242dfd791c11c79bc79c1cbadac52adc2
Smoke del binario empaquetado OK
Reglas economicas de Caja sin cambios
Arqueo, administrador, correo de cierre y mail ops preservados
HUMAN_GATE-RC30-CONSOLIDACION-001 PASS sobre copia verificada de la base productiva
El original de la base quedo con el mismo sha256 e5de6f4068bbea9a0c0de695802ce090539d54cb33052a10fca28776e0c07078
Ensayo de migracion rc.15 -> rc.30 hecho por el binario empaquetado sobre esa copia: 015 a 021, integridad ok
INSTALACION REALIZADA transaccional: zip y exe verificados por hash antes de tocar nada
Backup preinstall bc-caja-preinstall-1.0.0-rc.30-20260817-181556-179677.sqlite3 verificado
rc.15 preservada en BC-Caja-Pilot.previous-rc15 y paquete de retorno disponible
Post-install sobre la base productiva: 21 migraciones, integrity_check ok, foreign_key_check 0
Filas 2 dias / 12 movimientos / 8 pedidos / 10 items y montos (6400000, 2200000, 250000) sin cambios
exe instalado en disco sha256 identico al construido
Correo deshabilitado y outbox sin envios tras instalar
Rollback vigente mientras se conserven el backup preinstall y BC-Caja-Pilot.previous-rc15
main promovido por fast-forward, sin force-push
