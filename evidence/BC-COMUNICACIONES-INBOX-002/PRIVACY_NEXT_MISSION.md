# BC-COMUNICACIONES-PRIVACY-003 — especificación siguiente

Implementar un importador local que lea una copia de exportaciones de chat sin modificar el
original, produzca una copia anonimizada y un reporte. Debe reemplazar nombres, teléfonos,
cédulas, emails y direcciones; conservar orden, intención y tiempos relativos; ejecutar un
segundo escaneo de PII residual; y rechazar escribir datos reales dentro del repositorio.

Criterios: fixtures totalmente ficticios, tests por cada clase de PII, reporte con conteos y
hash del origen (sin su contenido), salida fuera del repositorio por defecto y confirmación
explícita cuando persistan candidatos sensibles. No se mezcla con `INBOX-002`.
