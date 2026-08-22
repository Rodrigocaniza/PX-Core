# ADR-0004 — El almacen de confianza es el del paquete y ninguno mas

Estado: aceptado — BC-SECURITY-INSTALLATION-BINDING-V1-001

## Contexto

El cliente verifica licencias con claves publicas. La pregunta es de donde las
saca. La opcion comoda —leerlas de un JSON en la carpeta de instalacion o en
`%LOCALAPPDATA%`— permite rotar la clave del emisor sin recompilar.

## Decision

Las anclas de confianza salen **exclusivamente** de
`modulos/seguridad/trusted_issuers.json`, que viaja dentro del paquete. No se
lee ninguna clave de confianza desde disco, ni desde variable de entorno en
produccion.

La unica puerta es `BC_SECURITY_TEST_TRUST`, y esta cerrada por construccion en
el ejecutable: si `sys.frozen` esta puesto —lo que hace PyInstaller— se ignora.
Existe para que las pruebas emitan con su propia clave sin firmar nada con la
de produccion.

## Fundamento

Un cliente que acepta anclas nuevas desde un archivo que esta a su lado no esta
atado a nada. Quien copia la carpeta a otra PC tambien puede dejar ahi su clave
publica y firmarse la licencia que quiera. Toda la cadena —binding, lease,
revocacion— se apoya en que la firma solo la puede producir el emisor; una
puerta de "agregar emisor" convierte esa cadena en decoracion.

Rotar la clave del emisor pasa a exigir una version nueva del paquete. Es un
costo real y aceptado: rotar una clave de firma es un evento raro y grave, y
que exija un despliegue es adecuado a su gravedad.

## Consecuencias

* `tools/bc_security_issuer.py almacen-de-confianza` regenera el archivo y hay
  que commitearlo. Es lo unico del emisor que viaja al cliente.
* Hay una prueba que fuerza `sys.frozen` y verifica que la variable de pruebas
  se ignora.
* Hay una prueba que verifica que el archivo publicado no contiene ninguna
  palabra que sugiera material privado.
