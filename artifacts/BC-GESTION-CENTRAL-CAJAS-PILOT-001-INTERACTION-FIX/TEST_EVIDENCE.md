# Evidencia QA

- Focalizadas: `12 passed`.
- Regresión completa: `211 passed`.
- Smoke interactivo de fuente: PASS.
- Unidades visitadas: las cuatro canónicas.
- Actualizar: PASS.
- Selección y reconocimiento: PASS.
- Cierre/reapertura y persistencia: PASS.
- Smoke interactivo del EXE empaquetado: PASS; requiere escritorio interactivo
  normal (Tk no inicializa si el proceso se fuerza a `WindowStyle Hidden`).

Las pruebas usan `Button.invoke`, eventos reales de `Combobox`/`Treeview` y
recreación real de ventanas Tk. Tcl/Tk requiere ejecución fuera del sandbox de
archivos debido a su instalación bajo Program Files del usuario.
