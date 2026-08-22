"""BC Seguridad V1: identidad de instalacion, licencia firmada y proteccion de datos.

Capa transversal. No conoce Caja, Historial ni Inventario: esos modulos la
consumen. La direccion de la dependencia es deliberada — si la seguridad
importara del dominio, cada modulo nuevo obligaria a tocarla.
"""

SECURITY_SCHEMA_VERSION = "bc.security.v1"
