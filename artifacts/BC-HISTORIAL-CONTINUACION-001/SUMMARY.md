# BC Historial — generación 1

Se preservó el commit histórico `e093842` mediante cherry-pick limpio como
`1900262` sobre `origin/main` `628749b`. Ambos tienen patch-id estable
`e60981e6ceabdeeb6f4f9befaaba9237289a8941`.

La continuación agrega una aplicación visual separada, búsqueda por CI/RUC,
nombre, teléfono y sobre/trabajo, ficha consolidada y cronología descendente
de ventas y trabajos. Lee la base canónica con `mode=ro` y `query_only`; no
crea base, migración ni fuente de verdad paralela.

Riesgo residual no bloqueante: una búsqueda parcial ambigua puede reunir
homónimos. La desambiguación queda como siguiente evolución cuando exista una
identidad maestra canónica.
