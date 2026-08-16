# Privacy Triage — FASE B (read-only)

Análisis sin modificar refs, sin reescribir historia y sin publicar copias
adicionales. Las extracciones para inspección se hicieron a un directorio
temporal fuera del repositorio y se eliminaron al terminar.

## Corrección del reporte previo

El commit señalado, `239e01b`, **no contiene ninguna imagen**. Sus cambios son
exclusivamente `.py` y `.sql`:

```
git diff-tree --no-commit-id --name-status -r 239e01b | grep '\.png$'  -> vacío
```

La afirmación anterior de que la captura contaminada quedó commiteada en
`239e01b` era incorrecta. La captura a pantalla completa que motivó el
hallazgo fue borrada antes del `git add` y nunca entró al índice.

El análisis completo de la cadena localiza las imágenes realmente afectadas en
**otros dos commits**.

## Inventario de imágenes de la cadena

| Commit | Imagen | Blob | Veredicto |
|---|---|---|---|
| `fdac03a` | `RC18/resumen-1366x768.png` | `0a882d95e79d` | Limpia (solo franja de barra de tareas con el rótulo de una ventana) |
| `fdac03a` | `RC18/resumen-1920x1080.png` | `aac87c0f8d93` | Limpia |
| `c4e5344` | `RC19/seguimiento-1366x768.png` | `8641c876b87f` | **Contaminada** |
| `c4e5344` | `RC19/seguimiento-1920x1080.png` | `dba62bfcd2d6` | Limpia |
| `7883901` | `RC20/envio-1366x768.png` | `43e0b0b6299f` | **Contaminada** |
| `7883901` | `RC20/envio-1920x1080.png` | `5bf92bf0b841` | **Contaminada** |
| `7883901` | `RC20/laboratorios-1366x768.png` | `36461564d400` | Limpia |
| `7883901` | `RC20/laboratorios-1920x1080.png` | `d56458f0e412` | Limpia |
| `b34ada1` | 8 imágenes de integración | — | Limpias (blobs verificados idénticos a las validadas) |

## Categorías de información externa visible

En las tres imágenes contaminadas:

- fragmentos de interfaz de otra aplicación en franjas de pocos píxeles en los
  bordes;
- rótulos de barra lateral y de barra de tareas;
- en dos casos, un fragmento de frase legible proveniente de una conversación.

**No** se observó ninguna de estas categorías:

- URLs completas;
- direcciones de correo;
- tokens, credenciales, contraseñas ni secretos;
- datos financieros o de identidad de terceros;
- documentos ni datos personales estructurados.

## Clasificación

**SENSITIVE — severidad baja.** No hay exposición de secretos.

## Alcance

Blobs alcanzables desde:

```
feature/bc-caja-rc19-seguimiento-pilar-laboratorios-001   (local + origin)
feature/bc-caja-rc20-alta-lote-pilar-abm-laboratorios-001 (local + origin)
release/bc-caja-rc18-rc20-integration-001                 (local + origin)
```

Repositorio remoto: `github.com/Rodrigocaniza/PX-Core`, privado.

## Recomendación

**Purga histórica: NO necesaria por seguridad.** No hay secretos que rotar ni
credenciales expuestas. Reescribir la historia exigiría `filter-repo` más
force-push sobre tres ramas ya CLOSED y publicadas, lo que contradice las
restricciones vigentes y aporta riesgo mayor que el contenido a remover.

Es, sin embargo, una decisión de privacidad del titular, no técnica. Dos
alternativas menos invasivas, en orden de costo:

1. **No hacer nada.** El repositorio es privado y el contenido son fragmentos
   sin valor informativo.
2. **Reemplazo hacia adelante**: regenerar las tres imágenes con el encuadre
   corregido y commitearlas en la rama de integración. Los blobs viejos siguen
   alcanzables desde las ramas CLOSED, así que no elimina la exposición: solo
   asegura que la versión vigente sea limpia.
3. **Purga real**: `git filter-repo` sobre los tres blobs, force-push
   coordinado de las tres ramas y reescritura de refs CLOSED. Solo si el
   titular considera que el fragmento de conversación lo amerita.

## Causa raíz, ya corregida

El recorte al rectángulo del diálogo usaba coordenadas Tk, que en Windows no
coinciden con píxeles de pantalla por el escalado DPI; el desfase dejaba
entrar franjas de lo que hubiera detrás. La sonda vigente encuadra la ventana
de la aplicación, verifica que el diálogo esté contenido y falla cerrado si no
lo está. Las capturas de `b34ada1` se generaron ya con ese mecanismo.
