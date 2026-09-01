# mex-orbit-testing

Las herramientas de **verificación** del proyecto: lo que se usa para saber si
algo está bien, no el algo en sí.

## Qué vive aquí y qué no

| | Dónde | Por qué |
|---|---|---|
| El **autotest del juego** (loop, chat, reconexión, portal, ajustes, ventanas, bestiario) | `mex-orbit-client` — `game/world.gd` + `tools/dev-run.ps1` | Es la puerta del cliente y se ejecuta con él; separarlo obligaría a mantener dos versiones del mismo recorrido |
| El **pipeline de arte** (recorte de croma, atlas, emisivas, anclas, normalizar modelos) | `mex-orbit-art/tools/` | Produce assets, no los juzga |
| El **banco de rendimiento 3D** | `mex-orbit-client` — `pruebas/banco_3d.tscn` | Es una escena de Godot, y un banco solo significa algo dentro del proyecto cuyos ajustes mide: renderizador, import de texturas, `project.godot` |
| **Validar y medir** antes y después | **aquí** | Se usa desde cualquier repo y no pertenece a ninguno |

La línea, cuando haya duda: **herramientas que se ejecutan solas van aquí; escenas
que necesitan el motor van en el repo del motor.**

## Herramientas

### `assets/validar-video.py` (retirado el 1-sep-2026)

Validaba los vídeos de los atlas animados. El cliente es 3D en los tres niveles y ya no hay atlas:
la validación de assets es solo `validar-modelo.py`.

### `assets/matiz.py`

El matiz de lo emisivo contra los tokens de la dirección N.

```bash
py -3 assets/matiz.py ../mex-orbit-art/source/renders/Portal.mp4 120
```

El color no es opinión. El portal llegó a **2 grados** del cyan que identifica al
jugador y la base en azul-violeta cuando su token es el cyan; ninguna de las dos
cosas chirría mirándolas, y las dos rompen el código de color.

### `assets/validar-modelo.py`

El contrato de un modelo 3D, comprobado **antes** de normalizarlo. Lee el GLB en
crudo: no necesita Blender ni Godot, solo PIL y numpy.

```bash
py -3 assets/validar-modelo.py ../mex-orbit-art/source/3d-models/crudo/vexor-texture.glb
py -3 assets/validar-modelo.py ../mex-orbit-art/source/3d-models/vexor.glb 200000 1024
```

Misma historia que `validar-video.py`, otro eje. El primer modelo que llegó de
Meshy incumplía cinco cosas a la vez y cada una se midió a mano: dos millones de
triángulos, tres texturas de 2048, venía **de pie** en vez de tumbado, y los
núcleos rojos estaban pintados en el albedo con la emisión a cero — se veían
rojos y no iban a brillar.

**Está calibrada contra ese Vexor**: el crudo saca seis rechazos y el master de
trabajo pasa con dos avisos.

- La **orientación** se juzga por la caja, no por metadatos: en un juego cenital
  el alto es siempre la dimensión menor. Meshy lee la imagen como un póster y
  devuelve el largo en vertical.
- El **pivote** importa aunque no se vea: descentrado, el bicho orbita en vez de
  virar, y eso no sale en una captura fija.
- La **luz cocida** es la única prueba que puede invalidar el enfoque entero —y
  la más débil de las seis. Sobre un atlas de UV un gradiente global no dice
  gran cosa, así que un desbalance alto **avisa, no rechaza**: es un «ábrelo y
  mira». En el Vexor da 0,03 contra un umbral de 0,22.
- **Sin animaciones y sin marcadores** son avisos, no rechazos: hay modelos que
  legítimamente no llevan ninguna de las dos cosas.

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
