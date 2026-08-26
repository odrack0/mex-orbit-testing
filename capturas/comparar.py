# -*- coding: utf-8 -*-
"""Compara dos capturas del autotest lado a lado.

Una foto fija NO demuestra que un shader o un atlas se MUEVA. El modo bestiario
del cliente saca dos fotogramas de cada bicho separados ~0,9 s
(`autotest-<code>.png` y `-b.png`); esto los pega para poder mirarlos.

Y medir pixeles que cambian NO sirve como sustituto: el fondo en paralaje se
mueve mas que el bicho y ahoga la senial. Se comprobo con un Skarnox sin shader
que "cambiaba" mas que un Gravon con el. Hay que mirar.

Uso:  py -3 capturas/comparar.py <code> [lado] [etiqueta]
Ej.:  py -3 capturas/comparar.py ferox 300
      py -3 capturas/comparar.py gravit 300 "GRAVIT MEDIA"
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

TOOLS = os.environ.get('CAPTURAS', 'C:/Tools')
CYAN = (0, 229, 255)
FONDO = (10, 10, 18)


def centro(im):
    """El bicho es lo mas brillante sobre el fondo casi negro del mapa. La
    MEDIANA y no la media: unas estrellas sueltas en una esquina no deben tirar
    del encuadre."""
    a = np.asarray(im.convert('L')).astype(np.int16)
    ys, xs = np.nonzero(a > 70)
    if len(xs) == 0:
        return im.size[0] // 2, im.size[1] // 2
    return int(np.median(xs)), int(np.median(ys))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    code = sys.argv[1]
    lado = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    etiqueta = sys.argv[3] if len(sys.argv) > 3 else code.upper()

    ra = '%s/autotest-%s.png' % (TOOLS, code)
    rb = '%s/autotest-%s-b.png' % (TOOLS, code)
    for r in (ra, rb):
        if not os.path.exists(r):
            print('falta %s — corre antes: .\tools\dev-run.ps1 -Bestiario' % r)
            return 1

    A = Image.open(ra).convert('RGB')
    B = Image.open(rb).convert('RGB')
    cx, cy = centro(A)
    caja = (cx - lado, cy - lado, cx + lado, cy + lado)
    out = Image.new('RGB', (lado * 4 + 24, lado * 2 + 34), FONDO)
    out.paste(A.crop(caja), (0, 34))
    out.paste(B.crop(caja), (lado * 2 + 24, 34))
    d = ImageDraw.Draw(out)
    d.text((8, 12), '%s  A' % etiqueta, fill=CYAN)
    d.text((lado * 2 + 32, 12), 'B (+0,9 s)', fill=CYAN)
    destino = '%s/comparar-%s.png' % (TOOLS, code)
    out.save(destino)
    print(destino, out.size)
    return 0


if __name__ == '__main__':
    sys.exit(main())
