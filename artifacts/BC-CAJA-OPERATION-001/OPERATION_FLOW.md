# Operation Flow

## Apertura y carga

```text
Menú Caja diaria
  → Cargar manual
  → Fecha + Unidad + Caja inicial
  → Abrir / Consultar Caja
  → completar campos
  → Enter / Guardar registro
  → SQLite commit
  → totales actualizados
  → foco vuelve a Descripción/Cliente
```

- Fecha, unidad y caja inicial permanecen para carga rápida.
- Un guardado en curso bloquea doble click concurrente.
- Un error conserva los valores ingresados.

## Corrección

```text
Historial → fecha/unidad → Consultar
  → Editar movimiento activo
  → formulario precargado
  → Guardar cambios
  → revisión UPDATE persistida
```

## Anulación

```text
Historial → Anular
  → motivo obligatorio
  → confirmación
  → estado VOIDED + revisión VOID
  → totales recalculados sin el movimiento
```

No hay borrado físico.

## Cierre

```text
Cargar manual → Cerrar Caja → confirmar
  → snapshot + closed_at
  → commit SQLite
  → backup local
  → modo consulta
```

No existe reapertura en el MVP.
