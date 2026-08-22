"""Primitivas criptograficas de BC, todas delegadas a `cryptography`.

Aca no se implementa criptografia: se elige. Cada funcion es una fachada fina
sobre una primitiva estandar, con el proposito (`info`, `aad`) fijado en un
solo lugar para que dos usos distintos no deriven por accidente la misma clave.

Las cuatro elecciones —Ed25519 para firmar, AES-256-GCM para cifrar,
HKDF-SHA256 para derivar por proposito y scrypt para la frase de
recuperacion— estan fundamentadas en `docs/adr/ADR-0002-primitivas-criptograficas.md`.
"""

from __future__ import annotations

import hmac
import os
from hashlib import scrypt, sha256

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ..errors import DataProtectionError, SignatureError


# Todo `info` de HKDF y todo dominio de hash arranca con esto. Sin un prefijo
# de dominio, una etiqueta que exista en dos formatos distintos deriva la misma
# clave en los dos, que es exactamente el accidente que se quiere evitar.
DOMAIN = "bc.security.v1"

AEAD_KEY_BYTES = 32
AEAD_NONCE_BYTES = 12
SECRET_BYTES = 32


# --------------------------------------------------------------------------
# Aleatoriedad
# --------------------------------------------------------------------------
def random_bytes(size: int) -> bytes:
    """CSPRNG del sistema. `random` no sirve para esto y no se usa en esta capa."""
    return os.urandom(size)


# --------------------------------------------------------------------------
# Derivacion
# --------------------------------------------------------------------------
def derive_key(secret: bytes, purpose: str, *, salt: bytes = b"", length: int = 32) -> bytes:
    """Clave de proposito unico a partir de un secreto maestro.

    `purpose` no es decorativo: entra en el `info` de HKDF, asi que la clave de
    datos y la de sincronizacion son criptograficamente independientes aunque
    salgan del mismo secreto. Comprometer una no entrega la otra.
    """
    if not purpose:
        raise ValueError("derive_key exige un proposito explicito")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt or None,
        info=f"{DOMAIN}/{purpose}".encode("utf-8"),
    ).derive(secret)


def derive_key_from_passphrase(passphrase: str, salt: bytes, *, length: int = 32) -> bytes:
    """Clave de recuperacion desde una frase escrita por una persona.

    scrypt y no HKDF: una frase no tiene la entropia de un secreto aleatorio, y
    lo unico que encarece adivinarla es un KDF con costo de memoria. Los
    parametros son los de uso interactivo de RFC 7914.
    """
    if len(salt) < 16:
        raise ValueError("el salt de recuperacion necesita al menos 16 bytes")
    return scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=2 ** 15,
        r=8,
        p=1,
        dklen=length,
        maxmem=96 * 1024 * 1024,
    )


# --------------------------------------------------------------------------
# Cifrado autenticado
# --------------------------------------------------------------------------
def aead_seal(key: bytes, plaintext: bytes, associated_data: bytes) -> bytes:
    """AES-256-GCM. Devuelve `nonce || ciphertext || tag` en un solo bloque.

    El nonce viaja adelante porque hace falta antes de descifrar y es publico.
    `associated_data` no se guarda: se reconstruye al abrir, y por eso ata el
    criptograma a su lugar — mover un valor cifrado de una fila a otra lo
    vuelve indescifrable en vez de silenciosamente valido.
    """
    if len(key) != AEAD_KEY_BYTES:
        raise ValueError("AES-256-GCM exige una clave de 32 bytes")
    nonce = random_bytes(AEAD_NONCE_BYTES)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, associated_data)


def aead_open(key: bytes, sealed: bytes, associated_data: bytes) -> bytes:
    if len(sealed) <= AEAD_NONCE_BYTES:
        raise DataProtectionError("criptograma truncado")
    nonce, body = sealed[:AEAD_NONCE_BYTES], sealed[AEAD_NONCE_BYTES:]
    try:
        return AESGCM(key).decrypt(nonce, body, associated_data)
    except InvalidTag as error:
        raise DataProtectionError("el criptograma no verifica en este contexto") from error


# --------------------------------------------------------------------------
# Firma
# --------------------------------------------------------------------------
def generate_signing_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def signing_key_bytes(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def signing_key_from_bytes(raw: bytes) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(raw)


def public_key_bytes(public_key: Ed25519PublicKey) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )


def public_key_from_bytes(raw: bytes) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(raw)


def key_id(public_key_raw: bytes) -> str:
    """Identificador estable de una clave publica: 16 hex de su SHA-256 con dominio.

    Sirve para elegir con que clave verificar sin probarlas todas, y para
    nombrar la clave en auditoria sin escribir la clave.
    """
    return sha256(f"{DOMAIN}/key-id".encode("utf-8") + public_key_raw).hexdigest()[:16]


def sign(private_key: Ed25519PrivateKey, message: bytes) -> bytes:
    return private_key.sign(message)


def verify(public_key: Ed25519PublicKey, signature: bytes, message: bytes) -> None:
    try:
        public_key.verify(signature, message)
    except InvalidSignature as error:
        raise SignatureError("la firma no verifica") from error


# --------------------------------------------------------------------------
# MAC
# --------------------------------------------------------------------------
def mac(key: bytes, message: bytes) -> bytes:
    return hmac.new(key, message, sha256).digest()


def mac_equal(left: bytes, right: bytes) -> bool:
    """Comparacion en tiempo constante. `==` sobre bytes filtra por donde difieren."""
    return hmac.compare_digest(left, right)


def digest(*parts: bytes) -> str:
    """Hash de dominio sobre partes separadas por longitud.

    Concatenar a secas permite que ("ab", "c") y ("a", "bc") den lo mismo; con
    la longitud delante, no.
    """
    accumulator = sha256(f"{DOMAIN}/digest".encode("utf-8"))
    for part in parts:
        accumulator.update(len(part).to_bytes(4, "big"))
        accumulator.update(part)
    return accumulator.hexdigest()
