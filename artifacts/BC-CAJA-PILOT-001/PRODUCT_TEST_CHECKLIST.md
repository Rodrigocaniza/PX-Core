# Checklist — Alucard / BC Product Tester

Registrar cada observación como `BUG`, `UX`, `MEJORA`, `IDEA` o `NO ACCIÓN`.

| Caso | Resultado esperado | Estado/observación |
|---|---|---|
| Apertura | La aplicación abre desde acceso directo/carpeta | |
| Caja inicial | Permite valor explícito; arrastra último cierre si queda vacío | |
| Carga rápida | Guardar una operación común requiere pocos pasos | |
| Efectivo | Suma correctamente al efectivo final | |
| Tarjeta | Registra Tarj./Cheq. sin aumentar efectivo físico | |
| Gasto | Reduce efectivo final | |
| Saldo | Conserva importe o texto `cancelado` | |
| Edición | Corrige el movimiento y actualiza totales | |
| Anulación | Exige motivo, conserva historial y revierte totales | |
| Cierre | Congela totales y crea backup | |
| Reinicio | Recupera el día y estado anterior | |
| Historial | Consulta día abierto/cerrado | |
| Error | Mensaje comprensible; no pierde lo escrito | |
| Velocidad/fricción | Registrar tiempo y pasos del flujo habitual | |

Formato recomendado: `TIPO | caso | pasos | esperado | observado | evidencia`.
