# ADR-0002 — Primitivas: Ed25519, AES-256-GCM, HKDF-SHA256, scrypt

Estado: aceptado — BC-SECURITY-INSTALLATION-BINDING-V1-001

## Contexto

La mision pide elegir alternativas **estandar, auditables y mantenibles**, y
prohibe explicitamente inventar seguridad. Hacian falta cuatro primitivas:
firma asimetrica para las licencias, cifrado autenticado para los datos,
derivacion de claves de proposito y derivacion desde una frase humana.

## Decision

| Uso | Primitiva | Por que |
|---|---|---|
| Firma de licencia y de revocacion | **Ed25519** | Clave y firma cortas (32 y 64 bytes), sin parametros que elegir mal, sin dependencia del generador de aleatoriedad al firmar. Una firma RSA con relleno mal elegido es un error clasico; Ed25519 no ofrece esa opcion. |
| Cifrado de columnas y de envolturas del llavero | **AES-256-GCM** | Cifrado autenticado: detecta la manipulacion en vez de devolver basura. Acelerado por hardware en cualquier PC de esta decada. Su dato asociado es lo que ata el criptograma a su lugar. |
| Derivacion de claves de proposito | **HKDF-SHA256** | Separa criptograficamente la clave de datos, la de sincronizacion y la del lease a partir del mismo secreto. Comprometer una no entrega las otras. |
| Frase de recuperacion | **scrypt** (RFC 7914, n=2^15, r=8, p=1) | Una frase escrita por una persona no tiene la entropia de un secreto aleatorio; lo unico que encarece adivinarla es un KDF con costo de memoria. |

Todas se toman de la biblioteca `cryptography`. En `crypto/primitives.py` no se
implementa ninguna: se las elige y se les fija el proposito en un solo lugar.

## Alternativas consideradas

**Implementar Ed25519 y ChaCha20-Poly1305 en Python puro**, para no agregar una
dependencia binaria al paquete de PyInstaller. Se descarto: es exactamente la
criptografia artesanal que la mision prohibe, sin tiempo constante y sin
auditoria externa, para ahorrar una dependencia que tiene rueda para Windows y
soporte de PyInstaller.

**HMAC compartido para las licencias.** Descartado por definicion del problema:
verificar exigiria que el cliente tenga la clave con la que se firma, y la
mision pide que la clave privada este fuera del cliente.

## Consecuencias

* `cryptography>=43,<47` entra a `requirements.txt` y al paquete. Si falta, BC
  falla al arrancar en vez de abrir sin proteccion — que es lo correcto: abrir
  sin cifrador sobre datos cifrados seria peor que no abrir.
* Todo `info` de HKDF lleva el prefijo de dominio `bc.security.v1/`. Dos usos
  distintos no pueden derivar la misma clave por coincidencia de etiqueta.
