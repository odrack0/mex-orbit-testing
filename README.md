# mex-orbit-testing

Las herramientas de **verificación** del proyecto: lo que se usa para saber si
algo está bien, no el algo en sí.

## Qué vive aquí y qué no

| | Dónde | Por qué |
|---|---|---|
| El **autotest del juego** (loop, chat, reconexión, portal, ajustes, ventanas, bestiario) | `mex-orbit-client` — `game/world.gd` + `tools/dev-run.ps1` | Es la puerta del cliente y se ejecuta con él; separarlo obligaría a mantener dos versiones del mismo recorrido |
| El **pipeline de arte** (recorte de croma, atlas, emisivas, anclas) | `mex-orbit-art/tools/` | Produce assets, no los juzga |
| **Validar y medir** antes y después | **aquí** | Se usa desde cualquier repo y no pertenece a ninguno |

## Herramientas

### `assets/validar-video.py`

La batería completa sobre un vídeo de asset, **antes** de meterlo al pipeline.
Croma, encuadre, costura del bucle, sub-bucle y sugerencia de celda.

```bash
py -3 assets/validar-video.py ../mex-orbit-art/source/renders/Ferox.mp4 12 190
```

Cinco vídeos se rechazaron por el mismo tipo de fallo y cada vez se midió a mano.
Un `APTO` no garantiza que el asset se vea bien —eso hay que mirarlo—, pero un
`RECHAZAR` ahorra el viaje entero de exportar, integrar, capturar y descubrirlo.

**Está calibrada contra los assets que ya pasaron**, y eso encontró dos fallos en
su primera versión: rechazaba al Ferox y al Vex, que llevan días en el juego.

- La **deriva del centroide** no se juzga en píxeles sueltos sino en **porcentaje
  del tamaño del bicho**. Un Ferox de 990 px que despliega guadañas mueve su
  centroide 31 px sin moverse del sitio: la forma cambia y el centro de masa la
  sigue. Eso es un 3% y es normal.
- El **sub-bucle** necesita **dos** condiciones, no una. Comparar solo contra el
  vídeo entero decía que "0..11 cierra igual de bien" cuando el entero cerraba a
  6,6× — cierto y completamente inútil. El tramo tiene que cerrar bien *en
  absoluto* **y** tan bien como el entero.

### `assets/matiz.py`

El matiz de lo emisivo contra los tokens de la dirección N.

```bash
py -3 assets/matiz.py ../mex-orbit-art/source/renders/Portal.mp4 120
```

El color no es opinión. El portal llegó a **2 grados** del cyan que identifica al
jugador y la base en azul-violeta cuando su token es el cyan; ninguna de las dos
cosas chirría mirándolas, y las dos rompen el código de color.

### `capturas/comparar.py`

Pega los dos fotogramas que el modo bestiario saca de cada bicho (separados
~0,9 s) para poder mirarlos lado a lado.

```bash
py -3 capturas/comparar.py ferox 300
```

Una foto fija **no** demuestra que algo se mueva. Y medir píxeles que cambian no
sirve como sustituto: el fondo en paralaje se mueve más que el bicho y ahoga la
señal — se comprobó con un Skarnox sin shader que "cambiaba" más que un Gravon
con él. Hay que mirar.

## Lo que NO se guarda

Los parches de un solo uso —los scripts que editan un archivo y se tiran— no
entran. Se escriben, se ejecutan y desaparecen con la sesión, y está bien: su
resultado ya vive en el commit que produjeron.

Lo que sí entra es lo que se **vuelve a necesitar**. La señal de que algo
pertenece aquí es haberlo escrito dos veces.
