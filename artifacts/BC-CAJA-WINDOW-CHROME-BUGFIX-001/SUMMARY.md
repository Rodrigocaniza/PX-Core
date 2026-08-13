# BC-CAJA-WINDOW-CHROME-BUGFIX-001

Base exacta: `2faa91c00528c2ecd979d8e61944448b77b60e73`.

Causa raíz: la geometría inicial usaba el tamaño completo de pantalla y origen
`+-8+-31`, desplazando el marco no-cliente fuera del monitor. El resultado
visual era borderless/fullscreen aunque Tk no activara fullscreen.

La ventana ahora declara explícitamente `overrideredirect(False)` y
`-fullscreen False`. En producción inicia maximizada mediante
`state("zoomed")`, conservando el chrome nativo de Windows.

