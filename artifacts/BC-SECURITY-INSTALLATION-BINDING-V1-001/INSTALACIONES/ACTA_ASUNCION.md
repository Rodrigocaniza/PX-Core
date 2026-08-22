# Acta de instalacion — ASUNCION

Se completa **durante** la instalacion, no despues de memoria. Un paso sin
resultado anotado cuenta como no hecho.

| | |
|---|---|
| Sucursal | **ASUNCION** (`--sucursal ASUNCION`) |
| Etiqueta de enrolamiento | `Optica ASUNCION - Caja 1` |
| Organizacion | `optica` |
| Lease / gracia | 365 / 180 dias |
| Paquete | `BC-CAJA-1.0.0-rc.33-win64.zip` — sha256 `20c298f5948c97ed99583e74eec9434f045eda340379d9a375777638e127bfa5` |
| Instructivo | `docs/INSTALACION_SEGURIDAD_EN_LA_OPTICA.md` |
| Fecha | ____________ |
| Quien instala | ____________ |
| PC (nombre de red) | ____________ |

---

## Antes de salir de Casa

- [ ] `python tools/verificar_paquete.py releases/BC-CAJA-1.0.0-rc.33-win64.zip` → `PAQUETE_OK`
- [ ] El respaldo de la clave del emisor **ya no esta** en la PC de Casa
- [ ] Pendrive vacio + papel + lapicera

---

## Los doce pasos

| # | Paso | Tiene que decir | Resultado | Hora |
|---|---|---|---|---|
| 0 | Requisitos (PC definitiva, 029-032 aplicadas, sin caja abierta) | los cinco tildados | | |
| 1 | Instalar paquete y abrir BC una vez | abre normal | | |
| 2 | `estado` | `tablas de seguridad : si` / `enrolada : no` | | |
| 3 | BC funciona con datos reales | historial y pedidos como siempre | | |
| 4 | Respaldo manual a pendrive + segunda copia | la copia abre en un visor SQLite | | |
| 5 | `enrolar --etiqueta "Optica ASUNCION - Caja 1"` | installation_id + frase mostrada una vez | | |
| 5b | **Frase anotada en papel y leida en voz alta** | si / no | | |
| 6 | Emitir licencia y `instalar-licencia`, `verificar` | `ALLOW / OK` | | |
| 7 | `proteger-datos` (ensayo) | cantidad en claro con sentido | | |
| 7b | `proteger-datos --confirmar --actor "..."` | `quedan en claro: nada` | | |
| 8 | `BC-Caja.exe --security-check` | `cifrado_en_disco=si filtracion=no planilla=sellada` | | |
| 9 | Las cinco comprobaciones a mano | las cinco en verde | | |
| 10 | **Prueba de copia en otra PC** | **no autoriza y no abre** + `bcx1:` en la base | | |
| 10b | `auditoria` en la PC de la Optica | el intento con `MAQUINA_DISTINTA` | | |
| 11 | `revertir-datos --confirmar` y volver a proteger | vuelve a claro y vuelve a cifrar | | |
| 12 | Cierre: borrar licencia del pendrive, guardar frase afuera | hecho | | |

---

## Datos que quedan de esta instalacion

```
installation_id      : ____________________________________
license_id           : ____________________________________
dek_id               : ____________________________________
lease vence          : ____________________________________
respaldo previo (7b) : Backups\pre-seguridad-________-bc_caja.sqlite3
valores protegidos   : ____________________________________
informes sellados    : ____________________________________
```

Frase de recuperacion: **en papel, fuera de la Optica.** No se escribe aca ni en
ningun archivo.

---

## Paso 10 — lo unico que Casa no pudo probar

Todo el resto del slice se verifico contra los ejecutables antes de viajar. Que
el secreto sellado con DPAPI **no abra en otra PC** no se pudo comprobar sin una
segunda computadora fisica.

```
Resultado en la segunda PC : [ ] DENY, no abrio     [ ] ABRIO  <-- avisar YA
Motivo que mostro          : ____________________________________
La base copiada mostraba   : [ ] bcx1:...   [ ] texto legible  <-- avisar YA
```

Si cualquiera de las dos casillas de aviso queda marcada: **no se instala PILAR**
hasta entender por que.

---

## Firma

```
Instalo        : ____________________
Presente por la Optica : ____________________
Fecha y hora de cierre : ____________________
```
