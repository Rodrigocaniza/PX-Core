# Data Path Report

La aplicación ya no depende del current working directory ni de la carpeta del código.

## Windows predeterminado

```text
%LOCALAPPDATA%\BC\Caja\
  bc_caja.sqlite3
  Backups\
  Logs\
```

## Override operativo

Variable: `BC_CAJA_DATA_DIR`.

Al definirla, toda la estructura se resuelve dentro de esa ruta absoluta. Esto permite instalación/empaquetado sin mover datos durante una actualización del programa.

Fallback no Windows: `$XDG_DATA_HOME/bc-caja` o `~/.local/share/bc-caja`.

Los tests con database explícita derivan sus backups junto a esa DB temporal y nunca usan la ruta productiva.
