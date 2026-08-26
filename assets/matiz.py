# -*- coding: utf-8 -*-
"""Mide el matiz de lo EMISIVO de un asset contra los tokens de la direccion N.

El color no es opinion: el portal llego a 2 grados del cyan que identifica al
JUGADOR, y eso rompe el codigo de color aunque a nadie le chirrie mirandolo. La
base llego en azul-violeta cuando su token es el cyan. Medirlo cuesta segundos.

Se ignoran los nucleos quemados (el percentil alto sale blanco y no dice nada) y
lo poco saturado (el casco gris no es emisiva). Lo que queda es el acento.

Uso:  py -3 assets/matiz.py <imagen.png | video.mp4> [fotograma]
"""
import colorsys
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

TOKENS = [
    ('cyan    (jugador y UI)', '00E5FF'),
    ('violet  (portales)', 'A78BFA'),
    ('warn    (numeros)', 'FFC85C'),
    ('hostile (peligro)', 'FF3D6E'),
    ('hp      (vida)', '3DF58C'),
    ('shield  (escudo)', '4DA6FF'),
]


def cargar(ruta, fot):
    if ruta.lower().endswith(('.mp4', '.mov', '.webm')):
        d = tempfile.mkdtemp(prefix='matiz_')
        subprocess.run(['ffmpeg', '-v', 'error', '-i', ruta, '-vf', 'select=eq(n\,%d)' % fot,
                        '-fps_mode', 'passthrough', '-frames:v', '1',
                        os.path.join(d, 'f.png')], check=True)
        return Image.open(os.path.join(d, 'f.png'))
    return Image.open(ruta)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    im = cargar(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0)
    tiene_alfa = im.mode in ('RGBA', 'LA')
    a = np.asarray(im.convert('RGBA')).astype(np.float32)
    r, g, b, al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    # la pieza: por alfa si la hay, por croma si viene de video
    m = al > 40 if tiene_alfa else ((g - np.maximum(r, b)) <= 22)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    lo, hi = np.percentile(lum[m], 85), np.percentile(lum[m], 99.3)
    em = m & (lum > lo) & (lum < hi) & (sat > 0.25)
    if em.sum() < 50:
        print('no hay emisiva con color suficiente para medir')
        return 1
    mr, mg, mb = float(r[em].mean()), float(g[em].mean()), float(b[em].mean())
    hh, ss, _ = colorsys.rgb_to_hsv(mr / 255, mg / 255, mb / 255)
    print('emisiva: #%02X%02X%02X  ·  matiz %.0f  ·  sat %.2f  ·  %d px\n'
          % (int(mr), int(mg), int(mb), hh * 360, ss, int(em.sum())))
    filas = []
    for nom, hexv in TOKENS:
        R, G, B = (int(hexv[i:i + 2], 16) for i in (0, 2, 4))
        h2, _, _ = colorsys.rgb_to_hsv(R / 255, G / 255, B / 255)
        dif = min(abs(hh * 360 - h2 * 360), 360 - abs(hh * 360 - h2 * 360))
        filas.append((dif, nom, hexv))
    for dif, nom, hexv in sorted(filas):
        print('  %-24s #%s  %3.0f grados' % (nom, hexv, dif))
    print('\n  el mas cercano manda: si no es el token que le toca al asset, '
          'hay decision que tomar.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
