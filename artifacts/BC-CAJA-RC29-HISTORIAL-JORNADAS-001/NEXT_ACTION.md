# NEXT_ACTION — próxima sesión en la Óptica

Estado desde el que se reanuda: **BC Caja 1.0.0-rc.27 instalada, validada y
estable en producción**. No hay RC abierta. No hay rollback pendiente.

## Punto de partida

1. **Reanudar BC Caja desde el estado canónico real** — no desde supuestos:
   releer versión instalada, `VERSION.txt`, hash del EXE, esquema y Mission
   Leases antes de proponer nada.

## Trabajo previsto, en orden

2. **Revisión transversal de Pedidos**, con la filosofía *"qué requiere atención
   ahora"*. No es una pantalla más: es decidir qué se le muestra al operador
   como accionable en este momento y qué no debería estar compitiendo por su
   atención.

3. **Revisar la apertura de Caja**:
   - fecha y hora actuales tomadas automáticamente;
   - **no permitir elegir fecha** al abrir caja;
   - **Caja inicial visualmente destacada**.

4. **DatePicker compartido** — después de (3), no antes: la apertura de caja
   deja de usar selección de fecha, así que el componente compartido se define
   sobre las pantallas que sí la necesitan.

5. **FactuFácil** — queda posterior. No entra en esta tanda.

## Restricciones vigentes

- No tocar `main` directamente.
- No iniciar una RC nueva sin autorización explícita de instalación.
- No modificar producción fuera de un flujo de instalación autorizado.
- No limpiar evidencia útil: backups, carpetas `rollback-*` / `replaced-*` y
  artifacts se conservan.
- Los smokes de GUI siguen sin poder conducirse por automatización; la
  validación visual la aporta el usuario.
