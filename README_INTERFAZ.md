# PX-Core - Interfaz gráfica, fase 3

Esta actualización conecta dos funciones operativas de la interfaz
gráfica sin eliminar ni modificar la versión funcional por consola.

## Cómo abrirla

1. Copiar estos archivos dentro de la carpeta principal `PX-Core`.
2. Hacer doble clic en `iniciar_interfaz.bat`.
3. La primera vez se instalará automáticamente `CustomTkinter`.

También se puede abrir desde la terminal:

```powershell
py -m pip install -r requirements.txt
py interfaz.py
```

## Funciones conectadas

Ruta:

```text
Movimientos → Cargar día → Abrir Cargar día
```

Desde la pantalla gráfica ya se pueden registrar:

- Ingresos.
- Egresos.
- Transferencias internas.
- Depósitos internos.
- Cobros externos.

La fecha se completa una sola vez y se reutiliza en todos los movimientos
registrados durante esa carga. Cada movimiento se guarda inmediatamente.

También está disponible:

```text
Movimientos → Gestionar movimientos → Abrir movimientos
```

Desde la tabla gráfica se puede:

- Filtrar por fecha inicial y final.
- Filtrar por tipo de movimiento.
- Ver todos los movimientos.
- Consultar 10 registros por página.
- Modificar cualquier campo de un movimiento.
- Cambiar el tipo de un movimiento.
- Eliminar un movimiento con confirmación previa.

Los movimientos se ordenan desde el más reciente al más antiguo. Al
modificar o eliminar se utiliza la posición real del registro dentro del
archivo para no afectar otra línea.

## Qué conserva de la fase anterior

- Ventana principal moderna.
- Menú lateral permanente.
- Modo claro, oscuro o según el sistema.
- Panel con datos reales del mes actual:
  - Ingresos.
  - Egresos.
  - Utilidad.
  - Margen porcentual.
  - Fondo de estabilidad acumulado.
  - Préstamos activos.
- Navegación visual para:
  - Movimientos.
  - Recursos Humanos.
  - Socios.
  - Aprendizaje.
- Botón para abrir la versión por consola.

## Datos y compatibilidad

- No hay que volver a cargar datos anteriores.
- La interfaz y la consola usan el mismo `Datos/movimientos.txt`.
- Lo registrado gráficamente también aparece en la consola.
- Lo registrado por consola también aparece en la interfaz.
- `main.py` y los demás módulos continúan funcionando normalmente.
- El ZIP de actualización no contiene ni reemplaza la carpeta `Datos`.

## Próxima etapa

Conectar gráficamente **Ingresos y egresos adicionales** y la
administración de sus conceptos.
