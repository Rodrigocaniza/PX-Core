# Cómo se aplica esto en la Óptica

Lo único que necesita la base real es la **migración 029**. Es aditiva: crea dos
tablas que no existían y no toca ninguna. El resto —la pestaña, el servicio— es
código y viaja con Git.

**Nada de esto se corrió contra producción.** Se probó sobre una base local
armada en el estado 028, que es el que hay hoy allá.

## Antes

Cerrá BC Caja. La migración abre la base para escribir.

```
git fetch origin
git checkout feature/bc-optica-factufacil-caja-v1-016
```

## 1. Dry-run

```
python tools/factufacil_migracion_029_optica.py --salida DRY_RUN_OPTICA.txt
```

Sin `--confirmar` no escribe. Antes de decir nada comprueba:

- `integrity_check` ok y FK 0 **antes** de tocar nada;
- que las tablas de FactuFácil todavía no existan;
- que la **028** esté aplicada, o sea que la base viene de la línea correcta.

Si alguna falla, sale sin escribir.

Lo que tiene que imprimir del estado actual: **28 migraciones**, y los números de
la Óptica —3.596 artículos, 4.441 movimientos, ASUNCION 6.166, PILAR 2.260—. Si
esos no coinciden, parar y mirar por qué antes de migrar.

Si dice «La 029 ya está aplicada», ya está: no hay nada que hacer.

## 2. Aplicar

```
python tools/factufacil_migracion_029_optica.py --confirmar --salida APLICACION_PRODUCTIVA.txt
```

Antes de la primera escritura toma un **backup verificable** en
`...\BC\Caja\Backups\bc-caja-prefactufacil-<fecha>.sqlite3` y comprueba que tenga
el mismo contenido que la base. Si eso falla, no migra.

## 3. Post-checks

Los corre sola. Todo tiene que decir `OK`:

- `schema_migrations` registra la **029**, y pasa de 28 a 29;
- existen `factufacil_loads` y `factufacil_history`, y **ninguna otra tabla nueva**;
- días, entradas, entradas activas, suma de caja, `sale_items`, artículos,
  movimientos, ASUNCION y PILAR: sin cambio;
- `integrity_check` ok, FK 0, negativos 0;
- las tablas nuevas nacen **vacías**: no se inventó ninguna marca;
- volver a migrar no cambia nada.

## 4. Rollback

Copiar `bc-caja-prefactufacil-<fecha>.sqlite3` sobre `bc_caja.sqlite3`. El backup
se toma antes de escribir, así que revierte todo.

Si abortó por una guarda, no hace falta: salió antes de tocar la base.

## 5. Smoke, con la operadora mirando

Abrir BC Caja. Aparece la pestaña **FactuFácil** al lado de Seguimiento.

- El chip **PARA CARGAR** trae las ventas del período que no están marcadas.
  Ninguna anulada, ningún gasto, ninguna entrega a administración.
- Elegir una fila: abajo se lee la receta **completa**, sin cortes.
- **Copiar datos** → pegar en un bloc: un campo por línea, en el orden en que
  FactuFácil los pide.
- **Marcar como cargada** → la fila se va de PARA CARGAR y aparece en CARGADA con
  el nombre de quien la cargó.
- **Volver a Para cargar** pide motivo. Sin motivo no vuelve.
- Cerrar y volver a abrir BC Caja: el estado sigue ahí.

Y lo que hay que confirmar que **no** pasó: el total del día, el efectivo y la
cantidad de entradas son los mismos que antes de tocar la pestaña.

## Lo que NO hay que hacer

- **No cargar nada a mano en FactuFácil desde Caja.** La fila nace de la venta que
  ya está registrada; si falta una venta, se corrige la venta, no la lista.
- **No usar esto como consola administrativa.** La revisión de Sol sigue en
  Gestión Central. Acá la operadora marca lo que cargó, y nada más.
- **No aplicar V1-015 en la misma corrida.** Son independientes y cada una tiene
  su backup.
