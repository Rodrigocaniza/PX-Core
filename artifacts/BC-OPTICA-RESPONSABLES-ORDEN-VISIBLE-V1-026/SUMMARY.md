# BC-OPTICA-RESPONSABLES-ORDEN-VISIBLE-V1-026

**Estado:** COMPLETADA_EN_CASA · una consulta · sin migración, sin binario, sin la PC de la Óptica

Misión chica y el artifact es chico a propósito: inflarlo sería decir que pasó
más de lo que pasó.

Cierra `RESPONSABLES-DISPONIBLES-ORDENA-POR-COLUMNA-CRUDA`, que dejó anotado
V1-021 al arreglar el mismo defecto en la función de al lado:

> `responsables_disponibles()` de V1-020 tiene el mismo defecto de orden que se
> corrigió en `personas_para_comision()`. Es cosmético y es de otro slice, así
> que se deja anotado y no se tocó.

## El defecto

Dos funciones listan personas activas y decían lo mismo de dos maneras:

```python
# personas_para_comision — arreglada en V1-021
"SELECT id, COALESCE(NULLIF(TRIM(display_name), ''), username) AS visible ... ORDER BY visible"

# responsables_disponibles — no
"SELECT display_name, username ... ORDER BY display_name"
return [(fila["display_name"] or fila["username"]) for fila in filas]
```

La segunda ordena por una columna y muestra otra. Quien no tenga nombre visible
cargado se ordena por `NULL` —al principio— y se muestra por su usuario, en un
lugar que no se corresponde con nada de lo que está en pantalla. Y un nombre de
sólo espacios pasa el `or` y sale como un renglón en blanco.

## Lo que hay que decir, y que el finding original no decía

**Por la puerta de entrada normal esto no pasaba.** `create_user` hace
`nombre = display_name.strip() or usuario`: si el nombre visible viene vacío, lo
reemplaza por el usuario antes de escribir. Así que no se pudo construir el
fallo llamando a la API pública, y la lista salía bien igual.

Se unificó de todos modos, por dos razones concretas y no por prolijidad: la
fila puede llegar por otro camino —SQL directo, una importación, una migración
futura— y tener dos consultas que responden la misma pregunta de dos maneras es
exactamente cómo terminan dos pantallas mostrando listas distintas.

## La prueba

Escribe la fila por SQL, que es el único camino por el que hoy puede aparecer, y
se comprobó que **falla con la consulta vieja**:

```
assert 'zoe' in ['sol', '   ', 'Ana']
```

Ahí está el defecto entero en una línea: `'   '` era el nombre del responsable
que la pantalla iba a ofrecer, y `zoe` no aparecía por ningún lado.
