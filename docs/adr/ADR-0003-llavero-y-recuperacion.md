# ADR-0003 — Una DEK por base, con dos envolturas independientes

Estado: aceptado — BC-SECURITY-INSTALLATION-BINDING-V1-001

## Contexto

Hay que cifrar datos de pacientes sin poder perderlos. La mision lo dice de dos
maneras: "nunca almacenar la clave de datos al lado de la DB en texto claro" y
"no cifrar sin estrategia de backup/recuperacion". Las dos a la vez.

La tentacion era derivar la clave de datos del secreto de instalacion. Es mas
corto y no necesita llavero. Y es una trampa: re-enrolar la PC —o cambiarla,
que es exactamente lo que pasa cuando se quema— dejaria la base ilegible para
siempre.

## Decision

Una **DEK** (data encryption key) aleatoria por base, generada una vez, que
nunca se deriva de nada. Se guarda **envuelta** de dos maneras, en la tabla
`security_keyring` de la propia base:

```
DEK --AES-GCM con--> clave derivada del secreto sellado por DPAPI   (installation)
DEK --AES-GCM con--> clave derivada por scrypt de una frase escrita (recovery)
```

La frase se muestra **una sola vez**, al enrolar, y no se guarda en ningun
lado. Va a papel, fuera de la computadora.

## Por que el llavero vive en la base y no aparte

Porque tiene que **viajar con la base**. Un respaldo restaurado sin su llavero
seria un respaldo indescifrable, y eso es perdida de datos con otro nombre.

Que la DEK envuelta este al lado de los datos no la revela: envolverla es
precisamente lo que la vuelve inutil sin el secreto de la instalacion o sin la
frase. Lo que la mision prohibe es la clave **en claro** al lado de la base, y
eso no ocurre en ningun momento.

## Consecuencias

* Re-enrolar no obliga a recifrar un solo dato: se vuelve a envolver la misma
  DEK con el secreto nuevo (`rewrap_for_installation`).
* Recuperar en otra PC son tres pasos: enrolar la PC nueva, abrir con la frase,
  re-envolver. La DEK no cambia.
* Una envoltura **se desactiva, no se borra** — hay un disparador en la 033 que
  lo impide. Si la envoltura nueva resultara ilegible, la vieja sigue estando.
* Perder la frase **y** la PC es perder la base. Esta escrito en la salida del
  enrolamiento, en el CLI y en el instructivo de la Optica, y es el unico
  camino de perdida total que este diseno deja abierto.
