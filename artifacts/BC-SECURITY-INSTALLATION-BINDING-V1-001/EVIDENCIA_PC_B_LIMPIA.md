# Evidencia fisica PC-B — instalacion limpia

Estado informado para la notebook PC-B:

- se extrajo y ejecuto el ZIP canonico limpio;
- BC arranco y mostro login + `CONFIGURACION INICIAL SEGURA`;
- no aparecio `DENY`;
- no se creo administrador ni contrasena;
- la aplicacion se cerro sin continuar.

## Interpretacion

**PASS del comportamiento de instalacion limpia; NO es la prueba de clonacion.**

Una copia limpia no lleva `installation.json`, `installation.secret`,
`license.bclic` ni una base ya protegida pertenecientes a PC-A. Por contrato,
BC queda sin enrolar y permite llegar a la configuracion inicial. Exigir `DENY`
en ese caso seria romper la instalacion inicial legitima.

La prueba PC-B pendiente requiere copiar desde una PC-A real que ya haya dado
`ALLOW / OK`: carpeta instalada, `%LOCALAPPDATA%\BC\Security` y una copia
consistente de `bc_caja.sqlite3` ya protegida. En PC-B esa clonacion completa
debe dar `DENY` y la base copiada debe conservar valores `bcx1:`.

## Limite de esta sesion

La PC de Casa no tiene una instalacion PC-A enrolada y autorizada disponible.
No se genera un bundle sustituto con datos simulados ni se toca produccion.
