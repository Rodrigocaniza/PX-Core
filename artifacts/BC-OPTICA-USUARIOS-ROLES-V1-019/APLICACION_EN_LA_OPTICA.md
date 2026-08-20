# Cómo se aplica esto en la Óptica

Lo que necesita la base real es la **migración 030**. Aditiva: cuatro columnas en
`admin_users` y ninguna tabla nueva. El resto es código y viaja con Git.

**Nada de esto se corrió contra producción.** Se probó sobre una base local en
estado 029.

## Antes

Cerrá BC Caja.

```
git fetch origin
git checkout feature/bc-optica-usuarios-roles-v1-019
```

## 1. Dry-run

```
python tools/usuarios_migracion_030_optica.py --salida DRY_RUN_OPTICA.txt
```

Comprueba, antes de decir nada: `integrity_check` ok, FK 0, que las cuatro
columnas no existan todavía, y que la **029 esté aplicada**. Si la 029 no está
—porque todavía no se aplicó la de FactuFácil— **para**: aplicá primero la 029.

## 2. Aplicar

```
python tools/usuarios_migracion_030_optica.py --confirmar --salida APLICACION_PRODUCTIVA.txt
```

Backup verificable en `...\BC\Caja\Backups\bc-caja-preusuarios-<fecha>.sqlite3`
antes de la primera escritura, con su contenido comparado contra la base.

## 3. Post-checks

Los corre sola. Todo tiene que decir `OK`: 29 → 30 migraciones, exactamente
cuatro columnas nuevas, y sin cambio en días, entradas, suma de caja,
`sale_items`, artículos, movimientos, trabajos de Seguimiento, laboratorios,
FactuFácil y pedidos. Además imprime cada usuario: el que ya existía tiene que
seguir siendo `ADMIN` y ahora tener nombre.

## 4. Rollback

Copiar `bc-caja-preusuarios-<fecha>.sqlite3` sobre `bc_caja.sqlite3`.

## 5. Lo que hay que hacer después, y es importante

Abrir el panel de Administrador → **Usuarios y permisos** → cargar a las personas
reales de la Óptica, cada una con su rol.

**Hasta que existan, el desplegable de vendedora queda vacío y editable**: la
operadora escribe el nombre a mano. La caja no se rompe, pero conviene cargarlas
el mismo día.

Los cuatro nombres cableados —Ana, Belén, Carla, Diana— **desaparecen con esta
versión**. Las ventas viejas conservan el texto que guardaron; las nuevas eligen
de la lista real. Si alguno de esos cuatro era en realidad el nombre de alguien
de la Óptica, cargalo como persona y no cambia nada.

Quién tiene que poder entrar al panel necesita contraseña; una operadora que sólo
vende, no.

## Orden sugerido si se aplican varias

1. **029** — FactuFácil (V1-016)
2. **030** — usuarios (V1-019)
3. **V1-015** — limpieza de marcas-laboratorio

Cada una con su propio backup. No se mezclan en una sola corrida.
