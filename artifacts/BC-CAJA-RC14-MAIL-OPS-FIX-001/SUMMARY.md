# BC Caja RC14

Corrige la recuperación durable de cierres creados antes de configurar correo. Los estados `NOT_CONFIGURED` vuelven a la cola, toman el destinatario confirmado vigente y conservan idempotencia: un cierre, un correo.

La verificación incluye 199 pruebas, SMTP/TLS simulado, fallo y reintento, privacidad del PDF, smoke visual 1366x768 y consistencia de binarios.
