# Safe Closure Evidence — BC-CAJA-RC20-ALTA-LOTE-PILAR-ABM-LABORATORIOS-001

- Cadena final: regresión canónica → smoke GUI real → no regresión RC18 y RC19
  → Artifact Consistency → commit protegido → push verificado.
- Autorización aplicada: la instrucción de cierre de RC20 cubre commit y push
  protegidos. No apareció ningún HUMAN_GATE auténtico nuevo: los dos defectos
  detectados en captura real se corrigieron dentro del alcance y se
  reverificaron, sin necesidad de intervención.
- Pruebas finales: **327 PASS / 0 FAIL**.
- Smoke GUI real: PASS en 1920×1080 y 1366×768, ejercitando los dos diálogos
  contra los widgets, con `emails=0` y `new_closures=0` en todas las corridas.
- No regresión verificada: smoke RC19 y smoke RC18 reejecutados en verde.
- Matriz de validación exigida: 18 de 18 puntos cubiertos con prueba nombrada
  (ver `TEST_EVIDENCE.md`).
- Allowlist de publicación: dominio de lote, servicio, migración 017,
  persistencia, diálogos en `CajaDiaria.py`, dos módulos de pruebas nuevos,
  cinco pruebas de cadena de migraciones extendidas a 017, sonda
  `tools/capture_caja_rc20.py` y artifacts finales RC20.
- Exclusiones verificadas como vacías: `.test-tmp/**`, `.pytest_cache/**`,
  `build/**`, `dist/**` y **todo cambio de Comunicaciones**, intacto en el
  directorio principal de PX-Core.
- `main` no fue tocada: rama de misión propia sobre `c4e5344`.
- Capturas saneadas: se recortan al rectángulo del diálogo, de modo que no
  entra contenido ajeno del equipo en un artifact versionado.
- Staging: rutas explícitas solamente, `git diff --cached --name-status`
  revisado, control temporal vacío y `git diff --cached --check` limpio.
- Publicación: commit funcional `239e01b` y commit de cierre documental, push
  **sin force**.
- Instalación: **no ejecutada**, fuera del alcance autorizado. RC17 permanece
  como versión instalada y disponible.
