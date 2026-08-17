# Causa raíz

La versión `a8240ed6` renderizaba cada unidad como un `Frame` con etiquetas.
Esos widgets no tenían `command` ni eventos de clic y no existía una pantalla de
detalle o navegación de regreso. `Actualizar` sí ejecutaba código, pero no
mostraba confirmación visible. El reconocimiento de una alerta podía quedar
oculto porque `refresh_alerts` recreaba la misma condición inmediatamente.

No se encontró overlay, estado `disabled`, ruta de datos incorrecta ni diferencia
entre el código publicado y el paquete instalado.
