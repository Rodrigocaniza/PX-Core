# BC-CAJA-WINDOW-BUGFIX-001

Base exacta: `50cc8973252bb59baf66f60faff74bee3baf068e`.

Causa raíz: `bc_caja.py` creaba un root oculto y Caja como `CTkToplevel`;
además `CajaDiaria.py` aplicaba `transient` y `grab_set`, convirtiendo la
ventana principal en un diálogo modal.

Corrección: el entrypoint autónomo usa Caja como raíz real, resizable, con
mínimo 1100×680. X y Alt+F4 comparten cleanup idempotente de repositorio,
`quit` y `destroy`. No se modificaron layout, negocio ni persistencia.

