# HUMAN_GATE — personas reales y tarifas de comisión

**Una sola cosa, y es la única del frente que no se puede hacer desde casa.**

## Qué se pide

Los nombres. Quién trabaja en la Óptica, con qué rol, en qué sucursal, quién
necesita entrar al sistema y quién no, y cuánto cobra cada persona por una
compostura. Nada de eso está en el repo ni se deduce de la base productiva.

## Por qué el código se detuvo acá y no un paso más adelante

La 030 creó la tabla de usuarios y no inventó ninguna persona. La 032 hace lo
mismo con las tarifas: sin política cargada, una compostura funciona entera y no
devenga nada, y el reporte la lista aparte. Las dos decisiones son deliberadas:
sembrar nombres de maqueta o montos que nadie autorizó en una base productiva es
peor que dejar el campo vacío.

Por eso hoy `admin_users` está en cero y la app pide «Configuración inicial
administrativa» al abrir. No es una regresión y no es un defecto pendiente: es el
estado correcto de una base que todavía no conoció a nadie.

## Qué se entrega

| | |
| --- | --- |
| `PROMPT.txt` | lo que hay que hacer, en tres pasos |
| `BC-OPTICA-PERSONAS-Y-TARIFAS.zip` | el formulario, la herramienta y las instrucciones |
| `MANIFEST.json` | procedencia y sha256 de cada pieza, precondiciones y rollback |
| `SUMMARY.md` | esto |

El ZIP se basta solo: adentro va la copia byte a byte de la herramienta que ya
vive en `tools/`, con su sha256 declarado en el manifest.

## Lo que NO hay que hacer

Ninguna migración: las cuatro están aplicadas y verificadas desde el 2026-08-20.
Ningún binario: la Óptica corre 1.0.0-rc.33. Nada en Gestión Central: la marca de
FactuFácil ya viaja sola desde esta misión.

## El riesgo, dicho entero

Se puede correr sin miedo dos veces: una persona que ya existe se actualiza en
vez de duplicarse. Y se puede mirar antes de aplicar: sin `--confirmar` no
escribe una sola fila y dice exactamente qué haría. Si aun así algo sale mal, el
punto único para volver atrás está en el manifest, y se probó restaurándolo.
