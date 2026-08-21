# BC Caja → BC Historial (integración V1)

> Estado: **V1 por proceso externo**. BC Caja **no** lee el histórico: lanza
> BC Historial como aplicación aparte, ya prefiltrada por el cliente que hay
> en pantalla.

## Qué hace

En la sección **CLIENTE Y COMPROBANTE** de la caja diaria hay un botón discreto
**"Ver historial"**. Al pulsarlo, BC Caja:

1. lee el nombre y la CI/RUC que están cargados en el formulario;
2. arma la línea de comandos de BC Historial;
3. lanza el ejecutable como proceso aparte y vuelve de inmediato.

BC Historial abre con la búsqueda ya aplicada y muestra la ficha de la persona.
BC Caja no queda esperando: el operador puede seguir cargando la venta con el
historial abierto al lado, y si cierra Caja el historial no se cae con ella.

## Contrato de invocación

```
"BC Historial.exe" --ci 1203712 --name "Fernando Gonzalez Leon"
"BC Historial.exe" --ruc 1203712-5 --name "Fernando Gonzalez Leon"
"BC Historial.exe" --name "Lilian Abdala"
```

Caja tiene un único campo "CI / RUC". Lo **único** que decide es en cuál de las
dos banderas mandarlo: **con guion es RUC, sin guion es CI**. El nombre siempre
viaja como respaldo.

La prioridad real (**CI válida → RUC → nombre**) y el descarte de documentos de
relleno (`1`, `111`, `222`) los aplica **BC Historial**, no Caja. Por eso un
cliente cargado con la CI placeholder de FactuFácil termina buscándose por
nombre sin que Caja tenga que saber nada de eso.

Esto es deliberado: **duplicar esa validación en Caja sería tener dos
verdades**, y la que manda es la del dueño del histórico.

## Dónde vive

```
modulos/historial_externo/
    launcher.py      ruta del ejecutable, armado de argumentos y lanzamiento
```

`CajaDiaria.py` solo importa `abrir_historial`, `hay_datos_de_cliente` y
`HistorialNoDisponible`. No hay rutas ni lógica de identidad en la UI.

## Ruta del ejecutable

Centralizada en `launcher.py`, en este orden:

1. variable de entorno `BC_HISTORIAL_EXE` (para instalaciones no estándar);
2. `C:\BC\factufacil-history\bc-historial\dist\BC Historial.exe`.

Si no aparece en ninguna, el botón muestra:

> **BC Historial no esta disponible en esta PC.**
> Pedi a soporte tecnico que lo instale. BC Caja sigue funcionando normalmente.

Nunca un stack trace, y **Caja no se rompe**: es un aviso y nada más.

## Lo que Caja NO hace

- No abre el SQLite histórico ni ejecuta SQL sobre él.
- No modifica el índice histórico ni los RAW de FactuFácil.
- No importa `bc_historial` (no hay dependencia entre repos).
- No copia el parser, la capa de identidad ni el servicio de consulta.
- El botón no guarda, edita ni toca la venta ni el cliente: solo lee los
  campos y lanza.

Todo esto está cubierto por tests en
`tests/caja_diaria/test_historial_externo.py`.

## Paso futuro (NO implementado)

La V2 natural es embeber el servicio de consulta en vez de lanzar un proceso:

```
BC Caja
  └── historical query service embebido
        └── bc_historial.query_service / identity  (read-only)
```

Eso permitiría mostrar el historial **dentro** de la ventana de Caja, sin
cambiar de aplicación. Requiere resolver antes:

- cómo se distribuye el paquete `bc_historial` junto con Caja (hoy son dos
  repos y dos ejecutables independientes);
- dónde vive el índice histórico y quién lo regenera;
- permisos: los datos clínicos (recetas) y los comerciales (montos, boletas)
  necesitan separarse, cosa que la capa histórica ya contempla con
  `get_prescriptions` aparte de `get_related_sales`.

Mientras eso no esté decidido, **V1 se queda como está**: acoplamiento por
línea de comandos, que es el más barato de revertir.

Ver también, en el repo de BC Historial:
`docs/INTEGRACION-BC-CAJA.md` y `docs/IDENTIDAD-V3.md`.
