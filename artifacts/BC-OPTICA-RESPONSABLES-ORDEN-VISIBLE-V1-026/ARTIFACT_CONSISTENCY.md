# Consistencia de artifacts — BC-OPTICA-RESPONSABLES-ORDEN-VISIBLE-V1-026

## Que el defecto no es alcanzable por la API pública

| Afirmación | Dónde se comprobó | Qué dice |
| --- | --- | --- |
| `create_user` nunca escribe el nombre visible vacío | `modulos/caja_diaria/application/admin_ops.py:505` | `nombre = str(display_name or "").strip() or usuario` |

Por eso el SUMMARY dice «unificación defensiva» y no «bug de producción». Se
comprobó antes de escribir la prueba, no después: si no, la misión habría
afirmado arreglar algo que no estaba roto por el camino normal.

## Que la prueba no es vacía

Se restauró la consulta vieja, se corrió la prueba nueva, y se volvió a aplicar
el arreglo. Salida literal:

```
>       assert "zoe" in disponibles, "sin nombre visible tiene que listarse por su usuario"
E       AssertionError: sin nombre visible tiene que listarse por su usuario
E       assert 'zoe' in ['sol', '   ', 'Ana']
1 failed in 0.57s
```

Con el arreglo: `1 passed`.

El `'   '` de esa lista es el punto entero de la misión: era el nombre de un
responsable que la pantalla iba a ofrecer para elegir.

## Suite

| Momento | Comando | Resultado |
| --- | --- | --- |
| antes de esta misión | `python -m pytest -q` | `1386 passed` |
| el módulo tocado | `python -m pytest tests/caja_diaria/test_v1020_trabajos_operativos.py -q` | `78 passed` |
| después | `python -m pytest -q` | `1387 passed in 216.22s` |

## Cierre

Se registra abajo, después del push, con la salida real de los comandos.
