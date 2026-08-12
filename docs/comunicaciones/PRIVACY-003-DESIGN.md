# BC-COMUNICACIONES-PRIVACY-003

## Decisión

El pipeline se integra como subpaquete de `modulos.comunicaciones`; no crea una base de
datos ni un segundo producto. La fuente se lee una vez, el resultado se valida y se publica
atómicamente fuera del repositorio. No existe conexión de red ni dependencia externa.

Flujo: adapter de formato → registros normalizados → detección → pseudonimización estable
por ejecución → escaneo residual → salida y reporte seguros. Cualquier formato, campo,
codificación, ruta o candidato residual no admitido cancela la operación. Un error nunca
incluye el valor original ni su ruta.

## Modelo de amenazas

Se consideran: commit accidental de exportaciones, envío a terceros, exposición en logs o
artifacts, sobrescritura del original, salida parcial, identificadores en metadata o adjuntos,
reidentificación por tabla reversible, errores de parser y falsa sensación de anonimato. Los
controles son exclusión Git, operación local, separación de rutas, escritura atómica,
mensajes constantes, segundo escaneo, fixtures sintéticas y ausencia deliberada de mapa
persistente. Riesgo residual: PII no cubierta por reglas, información contextual rara y
reidentificación por combinación de hechos conservados. Por eso el piloto futuro requiere
preflight y revisión controlada; el resultado no se declara anónimo en sentido absoluto.

## Clasificación y reglas

| Clase | Tratamiento |
|---|---|
| Identidad, teléfono, email, documento, dirección, usuario | pseudónimo tipado estable |
| Pedido, receta o factura identificable | pseudónimo tipado |
| Salud y contenido sensible reconocido | reemplazo `DATO_SALUD` |
| Metadata y nombre de adjunto | mismas reglas; metadata desconocida se conserva solo tras redacción |
| Timestamp del mensaje | se conserva para continuidad |
| Fecha de nacimiento | se reemplaza; otras fechas se conservan salvo contexto identificador |
| Monto, producto y sucursal | se conservan por valor analítico; riesgo contextual documentado |
| Empleados, clientes y terceros | todos los remitentes se pseudonimizan como `CLIENTE`; el rol no se infiere |

Los contadores representan valores únicos detectados, no los valores. La estabilidad existe
solo dentro de una ejecución/importación. No se genera tabla reversible.

## Retención, borrado y separación

Los originales quedan intactos y fuera del repositorio. La salida debe estar en otra carpeta,
también externa. El operador conserva únicamente el mínimo tiempo necesario: verificar,
usar y borrar la fuente mediante el procedimiento local aprobado; la aplicación no borra
automáticamente archivos que no creó. Las salidas se eliminan al terminar el análisis o al
vencer la política operativa futura, lo que ocurra primero. Un rechazo no publica salida
parcial. La cuarentena lógica consiste en el rechazo fail-closed; no copia PII.

## Formatos y extensión

Inicialmente: exportación WhatsApp TXT con líneas timestamp/remitente/texto y JSON
estructurado v1 (`messages`). Nuevos adapters deben implementar parse/render y pruebas de
malformados antes de habilitarse. El preflight examina localmente ruta, tipo, tamaño y hash,
sin incorporar ni imprimir contenido.

## Logging y artifacts

La CLI solo informa estado booleano. El reporte contiene versión, formato, SHA-256,
contadores, advertencias y rechazos; nunca valores. Ninguna fixture, prueba, captura,
evidencia o paquete puede contener PII real. Antes de Packaging debe ejecutarse el escaneo
anti-PII sobre paths autorizados y el ZIP.
