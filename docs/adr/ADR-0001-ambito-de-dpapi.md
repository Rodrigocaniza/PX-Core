# ADR-0001 — El secreto de instalacion se sella con DPAPI de MAQUINA

Estado: aceptado — BC-SECURITY-INSTALLATION-BINDING-V1-001

## Contexto

El secreto de instalacion es lo que ata BC a una computadora. Tiene que ser
imposible de recuperar en otra PC, y tiene que estar disponible en la PC
correcta sin pedirle nada a nadie: la Optica abre la Caja a las ocho de la
manana y no puede depender de que alguien tipee una frase.

Windows ofrece DPAPI (`CryptProtectData`) con dos ambitos:

* **usuario** — solo lo abre la misma cuenta de Windows;
* **maquina** — lo abre cualquier proceso de esa computadora.

## Decision

Ambito de **maquina** (`CRYPTPROTECT_LOCAL_MACHINE`), con entropia secundaria
derivada de los componentes obligatorios de la huella.

## Fundamento

La amenaza que la mision prioriza es la extraccion digital: copiar la carpeta,
el EXE, la base o el ZIP a **otra PC**. Los dos ambitos frenan eso por igual —
la clave maestra de DPAPI no viaja con los archivos.

Lo que los diferencia es el costo del lado legitimo. En la Optica hay mas de
una cuenta de Windows sobre la misma instalacion, y hay soporte que entra con
otra cuenta. Con ambito de usuario, iniciar sesion con otra cuenta habria dejado
BC sin poder abrir su propio secreto, con la base ya cifrada. Eso es una optica
cerrada por un motivo que no es una amenaza.

Lo que se pierde: en la PC autorizada, cualquier proceso local con permiso de
lectura sobre el archivo puede pedirle a Windows que lo abra. Se acota con la
entropia secundaria, que hay que saber reconstruir, pero no se elimina. Es un
compromiso deliberado: quien ya ejecuta codigo en la PC autorizada tiene
caminos mas directos que ese.

## Consecuencias

* La entropia secundaria usa **solo componentes obligatorios** de la huella.
  Si entrara un secundario, cambiar un disco volveria el secreto irrecuperable.
* No hay respaldo posible del secreto: por diseno no sale de la maquina. Lo que
  se respalda es la **frase de recuperacion de los datos** (ADR-0004), que es
  otra cosa y cubre el caso "la PC murio".
* No hay implementacion alternativa para otras plataformas. `default_sealer()`
  falla en vez de degradar: un "fallback portable" seria guardar el secreto con
  una clave derivable de lo que esta al lado del secreto.
