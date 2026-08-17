# BC Caja 1.0.0-rc.30 — tronco recuperado consolidado

Primera RC que tiene **todo junto**: el circuito de Seguimiento Pilar que estaba fuera de
`main` y la Apertura automática que estaba sólo en `main`.

## De dónde sale

Base: **el tronco recuperado**, `feature/bc-caja-rc21-tabla-seguimiento-logistica-001`
`491c363`, cuyo `VERSION.txt` declara **1.0.0-rc.27** e integra RC18→RC29.
**No se partió de `origin/main` ni se mergeó `main` completo**, tal como se decidió.

## Qué se portó de rc.15 (y qué no)

**Portado:**
- **Apertura de Caja automática.** La fecha la pone el sistema y no se tipea;
  `ABRIR CAJA DE HOY`; la hora sale de `CashDay.opened_at`; `Consultar otro día` carga el
  histórico en **sólo lectura**; `Caja inicial` destacada.
  Armonizado con el tronco: `estado_dia` (RC29) sigue siendo la **única** que traduce el
  estado —la hora se le concatena— y la cabecera conserva la escala que fijó RC18 para el
  ViewSonic 24" y los anchos de RC15-UX-OPERATIVA.
- **Contraste de acciones.** Disponible = sólido con texto blanco; no disponible = gris
  real `#DDE3EB` con borde propio; al pasar el mouse dice **por qué**. Aplicado a las tres
  acciones de RC24 (`Acción siguiente`, `Novedad`, `Más`) y a las de Pedidos. Para
  `Acción siguiente` **se reutiliza el motivo que ya calcula el dominio** en vez de inventar
  otro texto.

**Descartado a propósito:** la reescritura de la grilla de Pedidos de rc.15. El tronco trae
una posterior y mejor — RC22/RC23 anclaron el estado a la fila y eliminaron los chips
flotantes **como defecto**, y RC28 hizo que la alerta transporte su propio filtro y soporte
sucursal. Reintroducir la de rc.15 habría sido volver atrás.

Queda como slice futuro llevar al diseño del tronco lo que todavía aporta rc.15:
agrupación `ATRASADOS`/`PARA HOY`, `Última novedad` en la grilla y `Corregir estado` de
pedidos con lista cerrada derivada del dominio.

## Seguimiento: intacto

Circuito completo `ENVIADO_DESDE_PILAR → RECIBIDO_EN_ASUNCION → EN_LABORATORIO →
RECIBIDO_DEL_LABORATORIO → ENVIADO_A_PILAR → RECIBIDO_EN_PILAR → CERRADO`, con `NextAction`
como autoridad, `ATRASADO` y `QUEDA A CONFIRMAR` derivados, lista cerrada de transiciones,
recepción con discrepancias, ABM de laboratorios, vista por sucursal e historial.
Ni una línea del dominio ni del servicio de tracking cambió.

## La dependencia `fitz`

Se determinó antes de tocar nada: **PyMuPDF es dependencia de test, no de producción**.
Producción escribe los PDF con `reportlab` y los lee con `pypdf`; `fitz` se usa sólo en dos
archivos de test para **rasterizar la página** y comprobar que el encabezado se ve de
verdad. Se intentó migrar esos tests a `pypdf` y se descartó: `pypdf` extrae texto pero no
dibuja, así que se habría perdido esa verificación.

Resolución: se declaró en **`requirements-dev.txt`** (no en `requirements.txt`), con el
motivo escrito al lado. Verificado que **no entra al paquete**: 0 archivos de PyMuPDF en
`dist/BC-Caja`.

## Validación

| Nivel | Resultado |
| --- | --- |
| Focalizados (contraste + próxima acción + apertura) | 48 passed |
| Suite completa | **639 passed + 4 subtests** — incluidos los 2 archivos de PDF que antes no corrían |
| Contratos armonizados | `test_rc4`, `test_ux004`, `test_ux006`, `test_rc26`, `test_rc15_ux_operativa` |
| Visual 1920×1080 | apertura, consulta otro día, seguimiento, recepción con discrepancias, historial por jornada |
| Regresión 1366×768 | apertura |
| Migraciones | 21, sin agregar ninguna |
| Reglas económicas | sin cambios |
| Binario empaquetado | arranca; `zip_sha256` y `exe_sha256` en el MANIFEST |

## Producción: sin tocar

`origin/main` sigue en `65d2df4` (rc.15) y la instalación de esta PC sigue en **rc.15**.
rc.30 está empaquetada pero **no instalada**: espera `HUMAN_GATE-RC30-CONSOLIDACION-001`.

## Contratos de contrato que hubo que mover

Cinco tests de contrato de la línea recuperada apuntaban al literal viejo del estado o al
`state="normal" if ...` que ahora aplica el ayudante de disponibilidad. Se actualizaron
**preservando la intención** —nunca mostrar OPEN/CLOSED, y que el atraso no deshabilite el
botón principal— y dejando el porqué escrito en cada uno.

## Arquitectura siguiente (no implementada)

La consolidación deja el terreno para `Caja diaria | Trabajos | FactuFácil | Historial`,
con `Trabajos` agrupando Pedidos/Laboratorios, Envíos Pilar y Composturas. **Nada de eso se
empezó acá.**
