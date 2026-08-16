# BC Caja RC23 — El estado queda anclado a su fila

## Causa raíz

Los chips no eran parte de la tabla. Tanto Seguimiento como Pedidos los
dibujaban como **widgets `.place()` sobre el frame contenedor**, reposicionados
a mano leyendo `bbox()` de cada fila. Eso implica:

- viven en una capa distinta del contenido scrollable;
- no se recortan al viewport de la grilla;
- solo se reubican en los eventos que el código intercepta, así que cualquier
  repintado no previsto los deja flotando.

Los `PENDIENTE` de la captura son los de **Pedidos**, la implementación legacy:
los 15 pedidos TEST llevaron esa tabla de 2 a 17 filas y destaparon el defecto.

## Corrección estructural

**Seguimiento** deja de usar `ttk.Treeview`. Cada fila es ahora un widget real
dentro de un frame scrollable, y el chip es hijo de su propia fila: se
desplaza, se recorta, se repinta y se destruye con ella. No queda ninguna capa
que sincronizar, así que la clase de bug desaparece en vez de mitigarse.

**Pedidos** migra el estado a color de fila nativo del Treeview (`tag_configure`),
que también scrollea y repinta solo.

No queda ni un `posicionar_chips_*`, ni `chips_pedidos`, ni overlay de estado
en todo el archivo.

## Defectos encontrados al validar visualmente

Tres, ninguno visible para la suite:

1. Al reemplazar el bloque de la tabla se perdieron `COLORES_ESTADO_SEGUIMIENTO`,
   `COLOR_CHIP_*` y `MENSAJES_VACIO`, que el resto del código seguía usando: la
   pestaña habría reventado al abrir. Repuestas.
2. Encabezado y lista compartían celda del grid y el encabezado tapaba la
   primera fila (`S-001` no se veía). Separados en filas distintas.
3. La fila del encabezado tenía peso y, con `sticky="ew"`, el frame quedaba
   centrado dejando ~120 px de banda vacía arriba y abajo. Todo el sobrante va
   ahora a la lista.

La sonda incorpora una verificación **fail-closed**: recorre la cadena de
padres de cada chip y falla si alguno no cuelga de una fila.

## P2

Registrado como vínculo persistente `P2 → PILAR`, por la vía canónica y
auditado. Ya no es conocimiento informal.

```
P2 → PILAR (Rodrigo Cañiza) · PC → ASUNCION (MIGRACION-018) · PILAR → PILAR
```

## Circuito completo revalidado

```
etapa                          ASUNCIÓN                        PILAR
Pilar envía 15                 ve 15 · 15 por recibir          ve 0 · —
Asunción recibe                ve 15 · 15 por enviar a lab     ve 0 · —
3 al laboratorio, vencidos     ve 15 · 3 atrasados             ve 0 · —
encomienda en camino           ve 12 · 12 por enviar a lab     ve 3 · 3 por recibir
recibidos en Pilar             ve 12                           ve 0 · —
```

## Verificación

- Regresión canónica: **410 PASS, 0 FAIL**.
- Smoke GUI real en 1920×1080 y 1366×768, con detección de chips huérfanos.
- Escenario TEST devuelto a su punto de partida: 15 candidatos, 0 en circuito.
- Sin tocar lógica económica, cierres, correo, FactuFácil ni Comunicaciones.

## Instalación

Paquete `1.0.0-rc.23` construido y verificado. **No instalado**: había una
ventana de BC Caja abierta y la política es no cerrarla por la fuerza.

## Instalación ejecutada

| Item | Valor |
|---|---|
| Precheck instancias | 0 |
| Artifact | `BC-CAJA-1.0.0-rc.23-win64.zip`, 34.056.880 bytes, 1158 entradas, 18 migraciones |
| SHA256 ZIP | `82EEFD6E6F90F75F3F041E6C5E05C461647A0890500CC0D86B6C28140A13644D` |
| SHA256 EXE | `93B300E8608740541FE04B38DA55CA39A68544765F1F1F1A7CFE7FA187BD5013` |
| Backup | `Caja-RC23-preinstall-20260816d`, 33 archivos, `integrity_check=ok` |
| Rollback creado | `BC-Caja-Pilot.rollback-rc22-20260816d` |
| Rollbacks preservados | rc.22, rc.21, rc.20, rc.17, rc.16, rc.15 |
| Versión instalada | `BC Caja 1.0.0-rc.23` |
| `integrity_check` | ok |
| Migraciones | 001–018, sin migraciones nuevas |
| Datos | ninguna diferencia contra el precheck |
| Bindings | `P2 → PILAR`, `PC → ASUNCION`, `PILAR → PILAR` |
| Correos / cierres nuevos | 0 / 0 |
| Rollback usado | NO |

Smoke visual post-install en 1920×1080 y 1366×768: 15 filas con el estado
anclado dentro de cada fila, sin capas flotantes, y la sonda de chips
huérfanos en verde. Pedidos verificado sin overlays.

Escenario TEST en punto inicial: 15 candidatos, 0 en circuito, 3 laboratorios.
