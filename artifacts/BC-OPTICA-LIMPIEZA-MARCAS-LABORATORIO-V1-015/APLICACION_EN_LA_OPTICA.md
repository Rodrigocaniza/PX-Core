# Cómo se aplica esto en la Óptica

**Nada de esto se corrió contra producción.** Se preparó en Casa, sobre una copia
del catálogo. Estos son los pasos exactos para cuando estés frente a la máquina
de la Óptica.

## Antes de empezar

Cerrá BC Caja. La herramienta abre la base para escribir y dos escritores a la
vez es como se traba SQLite.

## 1. Dry-run, con la fuente corregida a mano

```
cd <repo>
python tools/limpieza_marcas_laboratorio_optica.py ^
    --fuente-corregida "C:\Users\Striker\Downloads\Inventario P2.xls" ^
    --salida DRY_RUN_OPTICA.txt
```

Sin `--confirmar` no escribe nada: imprime el plan y sale.

Si el archivo está guardado como `.xls` viejo, `openpyxl` no lo abre. Abrilo en
Excel y guardalo como `.xlsx` — es lo mismo que hizo V1-010, y el perfil de esa
misión lo dejó anotado.

Si no aparece el archivo, la herramienta corre igual: usa la evidencia registrada
en `EVIDENCIA_FUENTE_CORREGIDA.json` y lo dice en la primera línea del informe.
El plan sale idéntico salvo por `2000212`, que sin el archivo se queda en el
HUMAN_GATE.

## 2. Comparar contra lo que se preparó

El plan tiene que dar **28 / 2 / 1**: veintiocho a blanco, dos a
«Óptica Puppilent\`s», uno ambiguo. Está entero en `DRY_RUN.txt`, fila por fila.

Si con la fuente corregida `2000212` sale de `AMBIGUOUS`, es una mejora esperada
y no un desvío: significa que el archivo trajo su marca real.

Si aparece **cualquier otra diferencia** —un SKU de más, una clase distinta, una
marca destino que no existe— parar y mirar. La herramienta también aborta sola si
encuentra una marca-laboratorio que no está en su lista autorizada.

## 3. Aplicar

```
python tools/limpieza_marcas_laboratorio_optica.py ^
    --fuente-corregida "C:\Users\Striker\Downloads\Inventario P2.xls" ^
    --confirmar --salida APLICACION_PRODUCTIVA.txt
```

Antes de escribir una sola fila hace un backup verificable en
`...\BC\Caja\Backups\bc-caja-premarcas-<fecha>.sqlite3`, y comprueba que el
backup tenga el mismo contenido que la base. Si eso falla, no escribe.

## 4. Qué tiene que dar la verificación

La herramienta la corre sola y la imprime. Todo tiene que decir `OK`:

- sólo cambió `brand_id`, y sólo en los artículos del plan;
- **3.596** artículos, **2.829** activos;
- **4.441** movimientos · ASUNCION **6.166** · PILAR **2.260**;
- Caja: **12** entradas, **6.400.000**;
- `sale_items` sin cambio, y los laboratorios de las líneas históricas tampoco;
- marcas **136**, laboratorios **3**, artículos con laboratorio por defecto **24**;
- `integrity_check` ok, FK 0, negativos 0, huérfanos 0, efectos sin hecho 0;
- idempotencia: una segunda corrida no cambiaría nada.

## 5. Rollback

Si algo sale mal: cerrar todo y copiar el backup
`bc-caja-premarcas-<fecha>.sqlite3` sobre `bc_caja.sqlite3`. El backup se toma
antes de la primera escritura, así que revierte la misión entera.

No hace falta rollback si la herramienta abortó: cuando una guarda falla, sale
antes de escribir.

## 6. Después

Abrir *Comercial* y mirar un cristal cualquiera —`2000060 Organico UVX` sirve—.
Tiene que quedar sin marca y **con** su laboratorio sugerido. Y `2000070 Hilo`
tiene que quedar con marca «Óptica Puppilent\`s», seguir siendo
`SERVICIO_NO_STOCKEABLE` y no aparecer en stock.
