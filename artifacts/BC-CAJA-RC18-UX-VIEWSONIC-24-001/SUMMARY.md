# BC Caja RC18 — UX operativa en ViewSonic 24"

Base canónica: `BC Caja 1.0.0-rc.17` / `09344715fc54fc714b106fb4379a7721086fd7a6`.

Cambio limitado a presentación de la cabecera. No modifica reglas económicas,
cálculos, servicios, migraciones, SQLite, correo, cierre, pedidos, FactuFácil
ni datos.

## Objetivo

Reducir ruido visual y jerarquizar los importes que gobiernan la operación,
con foco en monitores ViewSonic 24" (1920×1080), conservando 1366×768.

## Qué cambió

- **Jerarquía de importes.** El resumen de caja separa los tres importes que
  deciden la operación (Venta, Efectivo, Esperado) de los tres de respaldo
  (Tarj./Transf., Gastos, Entregado). Los principales se dibujan sobre tarjeta
  blanca con la tipografía `fuente_kpi` del perfil; los secundarios quedan
  agrupados, atenuados y separados por un divisor.
- **`fuente_kpi` pasa a usarse.** El perfil full-hd ya declaraba `fuente_kpi:
  20` desde BC-CAJA-UX-1080P-001, pero la cabecera dibujaba todos los importes
  a 10 px fijos en ambos perfiles. Ahora el perfil gobierna el tamaño.
- **Chrome de cabecera al segundo plano.** El rótulo "RESUMEN DE CAJA", las
  etiquetas Fecha / Sucursal / Caja inicial, el aviso de trabajos, la insignia
  de estado y los botones ABRIR / CONSULTAR, Cerrar caja y Arqueo dejan de
  estar fijos en 9–10 px / 20–24 px y escalan con el perfil.
- **Cabecera dimensionada por contenido.** El alto deja de ser una constante
  por rama y se calcula sobre el alto real del resumen, porque el perfil
  tipográfico proviene de la pantalla y el alto de cabecera de la ventana.

## Defectos de presentación corregidos en el camino

- `CTkFrame` pide 200 px de alto por defecto: el divisor entre bloques, con
  `fill="y"`, estiraba la fila de la cabecera a 206 px y desplazaba los
  importes fuera del panel. Se le fija altura explícita.
- `CTkLabel` pide 28 px de alto sin relación con su fuente: sin altura
  explícita cada tarjeta ocupaba 59 px en todos los perfiles, anulando la
  jerarquía y desbordando la cabecera. Las etiquetas declaran altura propia.

## Costo vertical

Medido sobre GUI real, contra la línea base RC15/RC17:

| Perfil | Cabecera antes | Cabecera ahora | Costo |
|---|---|---|---|
| full-hd 1920×1080 | 52 px | 55 px | +3 px |
| compacto 1366×768 | 42 px | 44 px | +2 px |

El presupuesto vertical restante lo absorbe la grilla de movimientos, que
conserva su mínimo de cinco filas.

## Corrección fuera de alcance UX, incluida por bloquear la regresión

`representative_close()` (RC16, reutilizado por RC17) abría la jornada con
`utc_now()` y la cerraba en una fecha fija del 15-08-2026. Desde el 16-08-2026
el dominio rechazaba el cierre por anterior a la apertura y 5 pruebas de PDF
fallaban en canónico, antes de RC18. Se fija la apertura de la jornada
representativa; misma corrección en `tools/generate_caja_rc17_pdf_evidence.py`.

## Verificación

- Regresión canónica completa: **222 PASS, 0 FAIL**.
- Smoke GUI real 1920×1080 PASS y 1366×768 PASS, con importes reales.
- Sin correos enviados y sin cierres nuevos en ninguna corrida.
