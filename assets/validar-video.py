# -*- coding: utf-8 -*-
"""Bateria de validacion de un video de asset, ANTES de meterlo al pipeline.

Cinco videos se rechazaron por el mismo tipo de fallo y cada vez se midio a mano.
Esto es esa medicion, hecha una vez y bien. Un `APTO` aqui no garantiza que el
asset se vea bien —eso hay que mirarlo— pero un `RECHAZAR` ahorra el viaje
entero de exportar, integrar, capturar y descubrirlo.

Uso:  py -3 assets/validar-video.py <video.mp4> [fps] [screen_size]

`screen_size` es opcional y sale del JSON del bicho; con el, la herramienta
sugiere la celda del atlas (la leccion del Gravit: la celda se elige por lo que
el bicho mide en pantalla, no copiando la del anterior).

Lo que mide y por que:

  · CROMA — el fondo tiene que ser verde plano. El primer Gravon vino sobre
    negro y un casco de metal oscuro no se puede separar de ahi.
  · ENCUADRE — deriva del centroide RELATIVA al tamanio del bicho. En pixeles
    sueltos no dice nada: un Ferox que despliega guadanias mueve su centroide 31
    px sin moverse del sitio, porque la forma cambia y el centro de masa la
    sigue. El primer Vorax rechazado derivaba 55x37 sobre un bicho mas pequenio
    Y variaba su caja 70x196 — ahi si se paseaba.
  · COSTURA — el salto del ultimo fotograma al primero, medido CONTRA EL PASO
    NORMAL entre fotogramas, nunca en absoluto. Un video con mucho movimiento
    salta mucho en cualquier transicion; lo que delata un bucle roto es que la
    ultima salte MAS que las demas.
  · SUB-BUCLE — si el ciclo se repite dentro del video, medio video basta (el
    Vexor: 26 fotogramas en vez de 48, misma animacion, la mitad de VRAM). Pero
    un valle solo cuenta si cierra IGUAL DE BIEN que el video entero; si cierra
    peor no es un ciclo repetido sino un parecido, y recortar ahi quita
    movimiento real (el Ferox).
  · VAIVEN — si no hay ciclo en absoluto y el video es una rampa, se puede
    reproducir de ida y vuelta: el cierre sale perfecto por construccion y no
    cuesta un fotograma mas (el Vex). Solo vale si el movimiento NO tiene
    direccion privilegiada — los aros del Gravon tienen rotacion neta y al reves
    se mecerian; un ala que se abre no, porque cerrarse es su vuelta.
"""
import glob
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

VERDE = 22.0          # el mismo umbral de verdor que chroma-key.py y video-atlas.py
# La deriva se juzga RELATIVA al tamanio del bicho, no en pixeles sueltos. Un
# Ferox de 990 px que despliega guadanias mueve su centroide 31 px sin moverse
# del sitio: la forma cambia, el centro de masa la sigue. Eso es un 3% y es
# normal. El Vorax rechazado derivaba 55x37 sobre un bicho mas pequenio Y
# variaba su caja 70x196: ahi si se paseaba.
DERIVA_PCT = 8.0      # % del lado mayor de la caja
COSTURA_OK = 2.0      # veces el paso normal
COSTURA_MAL = 3.0


def extraer(video, fps):
    d = tempfile.mkdtemp(prefix='val_')
    subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-vf', 'fps=%d' % fps,
                    '-fps_mode', 'passthrough', os.path.join(d, 'f%04d.png')], check=True)
    return sorted(glob.glob(os.path.join(d, '*.png')))


def pieza(a):
    """La mascara del bicho: lo que NO es croma. El verdor se mide contra
    max(r,b) y no contra la media — si no, un nucleo cian brillante se recorta
    como si fuera fondo."""
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    return (g - np.maximum(r, b)) <= VERDE


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    video = sys.argv[1]
    fps = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    screen = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    fs = extraer(video, fps)
    n = len(fs)
    print('%s — %d fotogramas a %d fps (%.1f s)\n' % (os.path.basename(video), n, fps, n / float(fps)))

    problemas, avisos = [], []

    cx, cy, w, h, gris, verdor = [], [], [], [], [], []
    for f in fs:
        im = Image.open(f).convert('RGB')
        a = np.asarray(im).astype(np.int16)
        m = pieza(a)
        ys, xs = np.nonzero(m)
        if len(xs) == 0:
            problemas.append('un fotograma sale entero como croma: revisa el umbral o el fondo')
            return informe(problemas, avisos)
        cx.append(xs.mean()); cy.append(ys.mean())
        w.append(xs.max() - xs.min() + 1); h.append(ys.max() - ys.min() + 1)
        g_, r_, b_ = a[:, :, 1], a[:, :, 0], a[:, :, 2]
        verdor.append(float((g_ - np.maximum(r_, b_))[~m].mean()) if (~m).sum() else 0.0)
        gris.append(np.asarray(im.convert('L').resize((160, 90))).astype(np.float32))

    # ---- croma ----
    v = float(np.mean(verdor))
    fondo = 100.0 * float(np.mean([(~pieza(np.asarray(Image.open(f).convert('RGB')).astype(np.int16))).mean()
                                   for f in fs[:4]]))
    print('CROMA     verdor medio del fondo %.0f  ·  el fondo ocupa el %.0f%% del lienzo' % (v, fondo))
    if v < 40:
        problemas.append('el fondo no es croma verde plano (verdor %.0f): sobre negro o gris '
                         'no se puede recortar un casco oscuro' % v)

    # ---- encuadre ----
    dx, dy = max(cx) - min(cx), max(cy) - min(cy)
    vw, vh = max(w) - min(w), max(h) - min(h)
    lado = float(max(max(w), max(h)))
    pct = 100.0 * max(dx, dy) / max(lado, 1.0)
    print('ENCUADRE  deriva del centroide %.1f x %.1f px = %.1f%% del bicho  ·  caja %d-%d x %d-%d (var %d x %d)'
          % (dx, dy, pct, min(w), max(w), min(h), max(h), vw, vh))
    if pct > DERIVA_PCT:
        problemas.append('el bicho se desplaza por el lienzo (%.0f%% de su tamanio): la camara tiene '
                         'que estar FIJA y el bicho centrado' % pct)

    # ---- costura ----
    paso = np.array([np.abs(gris[i + 1] - gris[i]).mean() for i in range(n - 1)])
    ent = np.abs(gris[-1] - gris[0]).mean() / max(paso.mean(), 1e-6)
    mejor_corte, mejor_rel = n, ent
    for k in range(int(n * 0.72), n + 1):
        rel = np.abs(gris[k - 1] - gris[0]).mean() / max(paso[:k - 1].mean(), 1e-6)
        if rel < mejor_rel:
            mejor_rel, mejor_corte = rel, k
    print('COSTURA   entero %.2fx el paso normal' % ent, end='')
    if mejor_corte < n:
        print('  ·  recortando a %d: %.2fx' % (mejor_corte, mejor_rel))
    else:
        print()

    # ---- sub-bucle: solo cuenta si cierra IGUAL DE BIEN que el entero ----
    # DOS condiciones, y las dos hacen falta. Comparar solo contra el entero
    # dice que "0..11 cierra igual de bien" cuando el entero cierra a 6,6x — que
    # es cierto y no sirve de nada. El tramo tiene que cerrar BIEN en absoluto
    # (por debajo del umbral) Y tan bien como el entero (para saber que es un
    # ciclo repetido y no un parecido, la leccion del Ferox contra el Vexor).
    ref = min(ent, mejor_rel)
    cand = None
    for largo in range(max(12, n // 5), n):
        rel = np.abs(gris[largo - 1] - gris[0]).mean() / max(paso[:largo - 1].mean(), 1e-6)
        if rel <= COSTURA_OK and rel <= ref * 1.15 and (cand is None or largo < cand[0]):
            cand = (largo, rel)
    ahorro = 0 if cand is None else round(100 * (1 - cand[0] / float(n)))
    if cand and ahorro >= 15:
        print('SUB-BUCLE 0..%d (%.1f s, %.2fx) cierra igual de bien que el entero — %d%% menos de VRAM'
              % (cand[0] - 1, cand[0] / float(fps), cand[1], ahorro))
    else:
        print('SUB-BUCLE no hay uno que valga la pena: el ciclo no se repite dentro del video')

    # ---- veredicto de la costura ----
    final = min(ent, mejor_rel)
    if final > COSTURA_MAL:
        avisos.append('la costura es mala (%.1fx) y recortar no la arregla: o se pide de nuevo con '
                      '"el ultimo fotograma debe casar con el primero", o se reproduce en VAIVEN '
                      '(`"pingpong": true`) si el movimiento no tiene direccion privilegiada' % final)
    elif final > COSTURA_OK:
        avisos.append('la costura se notara un poco (%.1fx); aceptable si el bicho se mueve mucho' % final)

    # ---- celda sugerida ----
    if screen:
        util = max(max(w), max(h))
        for celda in (128, 192, 256, 320, 384, 512):
            if celda >= screen * 1.6:
                print('\nCELDA     %d px en pantalla -> celda %d (x%.1f). Recorte util %d px.'
                      % (screen, celda, celda / float(screen), util))
                break
    return informe(problemas, avisos)


def informe(problemas, avisos):
    print()
    for p in problemas:
        print('  RECHAZAR · %s' % p)
    for a in avisos:
        print('  REVISAR  · %s' % a)
    if not problemas and not avisos:
        print('  APTO · sin reparos. Mirar igualmente la silueta a tamanio de juego antes de exportar.')
    return 1 if problemas else 0


if __name__ == '__main__':
    sys.exit(main())
