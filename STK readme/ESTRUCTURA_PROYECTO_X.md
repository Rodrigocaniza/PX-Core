# ESTRUCTURA TÉCNICA — PROYECTO X / BC GESTIÓN

Actualizado a partir de `PX-Core.zip` el 29-07-2026.

## 1. Stack confirmado

- Lenguaje: Python.
- Interfaz principal: CustomTkinter 5.2.2.
- Componentes auxiliares: Tkinter/ttk.
- Persistencia: archivos TXT dentro de `Datos/`.
- Excel: openpyxl.
- PDF: reportlab.
- Sistema actual: aplicación de escritorio para Windows.
- Inicio gráfico recomendado: `iniciar_interfaz.bat`.
- Inicio gráfico manual: `py interfaz.py`.
- Inicio por consola: `py main.py`.

## 2. Árbol funcional

```text
PX-Core/
├── interfaz.py                 # Interfaz gráfica principal y navegación general
├── interfaz_rrhh.py            # Ventana gráfica de Recursos Humanos
├── main.py                     # Menú alternativo por consola
├── Movimientos.py              # Movimientos, cierres, préstamos y fondo
├── Socios.py                   # Retiros, saldos y distribución de socios
├── Funcionarios.py             # Legajos, salarios y gestión de funcionarios
├── Novedades.py                # Novedades laborales
├── Liquidaciones.py            # Liquidaciones y recibos
├── Informes.py                 # Informes visuales y exportación Excel/PDF
├── ImportadorExcel.py          # Importación y validación de planillas
├── ImportadorExcel_anterior.py # Copia anterior; no usar para cambios nuevos
├── datos.py                    # Lectura y escritura común de archivos TXT
├── Utilidades.py               # Utilidades generales
├── ideas.py                    # Módulo simple de ideas por consola
├── proyectos.py                # Módulo simple de proyectos por consola
├── requirements.txt            # Dependencias
├── iniciar_interfaz.bat        # Lanzador principal en Windows
├── Plantilla_Carga_Mensual_BC_Gestion.xlsx
├── assets/
│   └── logo/
│       └── logo.png            # Logo disponible; todavía debe integrarse en UI
├── Datos/
│   ├── movimientos.txt
│   ├── movimientos_adicionales.txt
│   ├── conceptos_adicionales.txt
│   ├── prestamos.txt
│   ├── cuotas_prestamos.txt
│   ├── fondo_estabilidad.txt
│   ├── funcionarios.txt
│   ├── novedades_funcionarios.txt
│   ├── liquidaciones.txt
│   ├── retiros_socios.txt
│   ├── inversiones.txt
│   ├── salarios_minimos.txt
│   ├── ideas.txt
│   ├── proyectos.txt
│   └── recibos_sueldo/
├── Respaldos/                  # ZIP automáticos; no editar manualmente
└── STK readme/                 # Documentación de negocio y arquitectura
```

## 3. Punto de entrada y navegación

### Interfaz gráfica

`interfaz.py`

- Clase principal: `AplicacionPXCore`.
- Componente auxiliar: `TarjetaIndicador`.
- Función de inicio: `iniciar()`.
- Ejecuta `AplicacionPXCore().mainloop()`.
- Abre Recursos Humanos mediante `interfaz_rrhh.abrir_recursos_humanos`.
- Importa y utiliza `Movimientos`, `Socios`, `Informes` e `ImportadorExcel`.
- También puede abrir la versión por consola.

### Recursos Humanos

`interfaz_rrhh.py`

- Clase principal: `VentanaRecursosHumanos`.
- Función pública: `abrir_recursos_humanos(...)`.
- Integra `Funcionarios`, `Novedades` y `Liquidaciones`.

### Consola

`main.py`

- Conserva menús alternativos.
- No es el punto principal para cambios visuales.
- Debe mantenerse compatible mientras continúe disponible.

## 4. Dependencias principales entre módulos

```text
interfaz.py
├── Movimientos.py
├── Socios.py
├── Informes.py
├── ImportadorExcel.py
├── interfaz_rrhh.py
└── datos.py

interfaz_rrhh.py
├── Funcionarios.py
├── Novedades.py
├── Liquidaciones.py
└── datos.py

ImportadorExcel.py
├── Movimientos.py
├── Socios.py
├── Liquidaciones.py
└── datos.py

Liquidaciones.py
├── Funcionarios.py
├── Novedades.py
├── Movimientos.py
└── datos.py

Socios.py
├── Movimientos.py
└── datos.py
```

## 5. Reglas para modificar el proyecto

1. No asumir rutas ni nombres de archivos.
2. Indicar siempre:
   - archivo exacto;
   - función o clase a buscar;
   - bloque que se reemplaza;
   - código que se pega;
   - forma de ejecutar y verificar.
3. Hacer cambios incrementales; no reescribir archivos completos.
4. Mantener compatibilidad entre interfaz gráfica y consola.
5. No duplicar persistencia: todos los módulos deben usar los archivos de `Datos/`.
6. Para lectura y escritura general, reutilizar `datos.leer_datos()` y `datos.guardar_datos()`.
7. No editar manualmente archivos de `Respaldos/`, `.git/` o `__pycache__/`.
8. No usar `ImportadorExcel_anterior.py` para funciones nuevas.
9. Mantener la opción `0` como Volver o Salir en menús de consola.
10. Antes de cambios grandes, crear respaldo.

## 6. Ubicación correcta para recursos gráficos

```text
assets/
└── logo/
    └── logo.png
```

Para integrar el logo:

- Ventana principal: modificar solamente `interfaz.py`.
- Recursos Humanos: modificar solamente `interfaz_rrhh.py` si también debe aparecer allí.
- Reportes PDF: modificar solamente las funciones de exportación de `Informes.py`.
- Ícono de ejecutable: agregar posteriormente un archivo `.ico` dentro de `assets/logo/`.

Las rutas deben construirse desde la carpeta del proyecto con `Path`, nunca con una ruta absoluta del equipo.

## 7. Archivos críticos

- `interfaz.py`: archivo muy grande; modificar únicamente funciones o métodos concretos.
- `Movimientos.py`: núcleo financiero; cualquier cambio puede afectar cierres e informes.
- `Socios.py`: distribución de utilidad, retiros y fondo.
- `datos.py`: capa común de persistencia; no cambiar sin revisar todos los módulos.
- `Datos/*.txt`: información real; proteger con respaldo antes de migraciones.
- `ImportadorExcel.py`: valida e inserta datos en varios módulos; probar siempre con copia.

## 8. Dependencias instalables

`requirements.txt`

```text
customtkinter==5.2.2
openpyxl>=3.1,<4
reportlab>=4,<5
```

Instalación:

```powershell
py -m pip install -r requirements.txt
```

Ejecución recomendada:

```powershell
iniciar_interfaz.bat
```

## 9. Estado confirmado del logo

El archivo existe en:

```text
PX-Core/assets/logo/logo.png
```

Todavía no se detecta una referencia a `logo.png` dentro de `interfaz.py`, por lo que el próximo cambio debe ser su integración visual sin mover el archivo.
