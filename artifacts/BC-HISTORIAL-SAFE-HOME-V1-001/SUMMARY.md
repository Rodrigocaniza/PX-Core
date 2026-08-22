# BC Historial — cierre SAFE desde Casa

- Rama canónica: `feature/bc-historial-multisucursal-v1-001`.
- Base detectada al iniciar: `eb414a38640177d2ff3f6691ff483b3ccbd9854b`.
- Implementación publicada: `2cd88689863a1153445f6194294bbef866935ff1`.
- Origin: sincronizado `0/0` después del push normal, sin force-push.
- Librarian: PASS.
- QA: PASS.
- Auditor adversarial: PASS.
- Dirigidos finales: 57 PASS.
- Regresión Caja: 1022 PASS, 37 skip ambientales previstos.
- CI remoto PR #14: PASS, run `32594536940`, 4m37s.

La política vigente es Admin global, operadora local y Visor Federado global
estrictamente read-only. La apertura exige un verificador externo de sesión;
Caja aporta `require_operator` y Seguridad BC puede aportar su binding sin que
Historial lo duplique. Los hechos sin sucursal se excluyen y el filtro local se
aplica en SQLite antes del límite.

No se desplegó en PC/P2, no se alteró una base productiva y no se generó
evidencia física. Único pendiente: ejecutar `PROMPT.md` en los hosts reales.
