# -*- coding: utf-8 -*-
"""Bateria de validacion de un modelo 3D, ANTES de meterlo al pipeline.

El primer modelo que llego de Meshy —el Vexor— incumplia cinco cosas del
contrato a la vez y cada una se midio a mano: dos millones de triangulos para un
bicho que se dibuja a 178 px, tres texturas de 2048 (48 MB de VRAM cuando su
atlas entero cuesta 11,7), venia DE PIE en vez de tumbado en el plano, y los
nucleos rojos estaban pintados en el albedo con la emision a cero, o sea que no
brillaban. Esto es esa medicion, hecha una vez y bien.

Mismo criterio que `validar-video.py`: un `APTO` no garantiza que el modelo se
vea bien —eso hay que mirarlo, y ademas en 3D el aspecto final lo pone la luz de
la escena, no el archivo— pero un `RECHAZAR` ahorra el viaje entero de
normalizar, importar, montar la escena y descubrirlo.

Lee el GLB en crudo: no necesita Blender ni Godot, solo PIL y numpy.

Uso:  py -3 assets/validar-modelo.py <modelo.glb> [tris] [lado_textura]

  tris          presupuesto de triangulos (por defecto 15000, el asset de juego)
  lado_textura  lado maximo de cada mapa (por defecto 512)

Para juzgar un MASTER de trabajo en vez de un asset de juego, subir los dos:
`py -3 assets/validar-modelo.py vexor.glb 200000 1024`.

Lo que mide y por que:

  · TRIANGULOS — medido: 15 000 son indistinguibles de 1 965 610 a tamanio de
    juego, porque el detalle vive en el mapa de normales y no en los poligonos.
    Lo que sobra no se ve y se paga entero.
  · TEXTURAS — tres mapas de 2048 son 48 MB de VRAM. A 512 son 3, que es cuatro
    veces menos que el atlas del mismo bicho. El lado se elige por lo que el
    bicho mide en pantalla, igual que la celda de un atlas.
  · ORIENTACION — Meshy interpreta la imagen como un poster y devuelve el modelo
    de pie, con el largo en vertical. En un juego cenital el ALTO es siempre la
    dimension menor; si no lo es, el modelo entra tumbado hacia donde no debe y
    la camara lo mira de canto.
  · PIVOTE — el giro es sobre el origen. Descentrado, el bicho ORBITA en vez de
    virar, y eso no se ve en una captura fija: aparece en cuanto gira.
  · EMISION — el material tiene que declararla. Meshy pinta las vetas y los
    nucleos en el albedo y deja emissiveFactor en cero: se ve rojo, pero no es
    luz, y el latido del bicho se pierde. Es lo que da caracter al Vexor (dos
    nucleos) y al Skarn (magma en las grietas).
  · LUZ COCIDA — si el albedo trae iluminacion horneada, la luz del mundo la
    ilumina otra vez y sale doble. Es la unica prueba que puede invalidar el
    enfoque entero, y la mas debil de las seis: sobre un atlas de UV un
    gradiente global no significa gran cosa. Un desbalance alto no es un
    rechazo, es un "abrelo y mira".
"""
import json
import os
import struct
import sys
from io import BytesIO

import numpy as np
from PIL import Image

TRIS = 15000          # presupuesto por defecto: el asset de juego
LADO = 512            # lado maximo por mapa
PIVOTE_MAX = 0.02     # el centro de la caja, a menos del 2% del tamanio del origen
DESBALANCE = 0.22     # gradiente global de luminancia que enciende el aviso


def leer_glb(ruta):
    """Devuelve (json, bytes del chunk binario). El GLB es cabecera de 12 bytes
    y luego chunks de (longitud, tipo, datos)."""
    with open(ruta, 'rb') as f:
        datos = f.read()
    if datos[:4] != b'glTF':
        raise ValueError('no es un GLB (falta la firma glTF)')
    doc, binario, off = None, b'', 12
    while off < len(datos):
        largo, tipo = struct.unpack_from('<II', datos, off)
        cuerpo = datos[off + 8:off + 8 + largo]
        if tipo == 0x4E4F534A:
            doc = json.loads(cuerpo.decode('utf-8'))
        elif tipo == 0x004E4942:
            binario = cuerpo
        off += 8 + largo + (-largo % 4)
    return doc, binario


def imagenes(doc, binario):
    """Cada imagen del GLB abierta con PIL, por indice."""
    salida = {}
    for i, img in enumerate(doc.get('images', [])):
        if 'bufferView' not in img:
            continue
        bv = doc['bufferViews'][img['bufferView']]
        ini = bv.get('byteOffset', 0)
        salida[i] = Image.open(BytesIO(binario[ini:ini + bv['byteLength']]))
    return salida


def triangulos(doc):
    total = 0
    for malla in doc.get('meshes', []):
        for prim in malla.get('primitives', []):
            if 'indices' in prim:
                total += doc['accessors'][prim['indices']]['count'] // 3
            elif 'POSITION' in prim.get('attributes', {}):
                total += doc['accessors'][prim['attributes']['POSITION']]['count'] // 3
    return total


def caja(doc):
    """Caja envolvente en coordenadas glTF (Y arriba), de los min/max que el
    propio accessor ya trae: no hace falta descomprimir un solo vertice.

    Se recorre por NODOS y acumulando la transformacion del padre, no por mallas
    sueltas. En un modelo partido cada ala guarda sus vertices relativos a su
    bisagra y su posicion vive en el nodo; sumando solo los accessors salia una
    caja mas estrecha que el bicho (1,31 en vez de 1,91) y el aviso de
    orientacion se disparaba solo."""
    lo = np.array([np.inf] * 3)
    hi = np.array([-np.inf] * 3)
    nodos = doc.get('nodes', [])

    def recorrer(i, off, esc):
        nonlocal lo, hi
        n = nodos[i]
        t = np.array(n.get('translation', [0.0, 0.0, 0.0]), dtype=float)
        s = np.array(n.get('scale', [1.0, 1.0, 1.0]), dtype=float)
        # Sin rotacion: los modelos del contrato no la llevan en los nodos, y
        # tenerla en cuenta pediria matrices completas para poca ganancia.
        off2, esc2 = off + t * esc, esc * s
        if 'mesh' in n:
            for prim in doc['meshes'][n['mesh']].get('primitives', []):
                idx = prim.get('attributes', {}).get('POSITION')
                if idx is None:
                    continue
                acc = doc['accessors'][idx]
                if 'min' in acc and 'max' in acc:
                    a = np.array(acc['min']) * esc2 + off2
                    b = np.array(acc['max']) * esc2 + off2
                    lo = np.minimum(lo, np.minimum(a, b))
                    hi = np.maximum(hi, np.maximum(a, b))
        for h in n.get('children', []):
            recorrer(h, off2, esc2)

    raices = set(range(len(nodos)))
    for n in nodos:
        for h in n.get('children', []):
            raices.discard(h)
    for i in sorted(raices):
        recorrer(i, np.zeros(3), np.ones(3))
    return lo, hi


def desbalance_luz(img):
    """Cuanto se va la luminancia de un lado a otro de la textura, en tanto por
    uno sobre la media. Un render proyectado con la luz de la escena horneada se
    delata aqui; un atlas de UV normal sale bajo."""
    a = np.asarray(img.convert('L'), dtype=np.float32)
    media = float(a.mean())
    if media < 1.0:
        return 0.0
    h, w = a.shape
    dx = abs(a[:, :w // 2].mean() - a[:, w // 2:].mean())
    dy = abs(a[:h // 2, :].mean() - a[h // 2:, :].mean())
    return float(max(dx, dy) / media)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    ruta = sys.argv[1]
    tope_tris = int(sys.argv[2]) if len(sys.argv) > 2 else TRIS
    tope_lado = int(sys.argv[3]) if len(sys.argv) > 3 else LADO

    doc, binario = leer_glb(ruta)
    imgs = imagenes(doc, binario)
    problemas, avisos = [], []

    print('MODELO  %s  (%.1f MB)' % (os.path.basename(ruta), os.path.getsize(ruta) / 1048576.0))
    print('        presupuesto: %d tris, texturas de %d' % (tope_tris, tope_lado))

    # --- piezas ---
    # Con la opcion "Dividir" de Meshy el modelo llega partido, que es lo que
    # hace falta para animar por rotacion de nodos en vez de por clave de forma.
    # Saberlo de un vistazo es lo primero que se mira al recibirlo.
    nodos_malla = [n for n in doc.get('nodes', []) if 'mesh' in n]
    print('\nPIEZAS       %d' % len(nodos_malla))
    for n in nodos_malla:
        m = doc['meshes'][n['mesh']]
        t = sum(doc['accessors'][p['indices']]['count'] // 3
                for p in m.get('primitives', []) if 'indices' in p)
        print('             %-20s %d tris' % (n.get('name', '(sin nombre)')[:20], t))
    # Un modelo con ESQUELETO no necesita venir partido: articula por pesos, y es
    # la forma buena — no deja costura en las bisagras, porque no hay corte. El
    # aviso de "una sola pieza" solo tiene sentido sobre una malla suelta y sin
    # huesos; sobre un modelo rigueado era sencillamente falso.
    huesos = []
    for s in doc.get('skins', []):
        huesos += [doc['nodes'][j].get('name', '?') for j in s.get('joints', [])]
    print('ESQUELETO    %s' % (', '.join(huesos) if huesos else 'ninguno'))

    if len(nodos_malla) == 1 and not huesos:
        avisos_piezas = ('una sola pieza y sin esqueleto: para articular hara falta partirla o '
                         'riguearla, y lo que este fusionado en la malla no se puede separar '
                         'sin inventar geometria')
    else:
        avisos_piezas = ''

    # --- triangulos ---
    tris = triangulos(doc)
    print('\nTRIANGULOS   %d' % tris)
    if tris > tope_tris:
        problemas.append('%d triangulos, %.0f veces el presupuesto de %d'
                         % (tris, tris / float(tope_tris), tope_tris))

    # --- texturas ---
    vram = 0.0
    print('TEXTURAS     %d mapas' % len(imgs))
    for i, im in sorted(imgs.items()):
        vram += im.size[0] * im.size[1] * 4 / 1048576.0
        marca = '  <-- pasa de %d' % tope_lado if max(im.size) > tope_lado else ''
        print('             %dx%d %s%s' % (im.size[0], im.size[1], im.mode, marca))
        if max(im.size) > tope_lado:
            problemas.append('textura de %d, el tope es %d' % (max(im.size), tope_lado))
    print('             ~%.1f MB de VRAM sin comprimir' % vram)

    # --- caja, orientacion y pivote ---
    lo, hi = caja(doc)
    ext = hi - lo
    centro = (hi + lo) * 0.5
    mayor = float(ext.max())
    # glTF es Y-arriba: X ancho, Y alto, Z largo
    print('\nCAJA         ancho %.3f  alto %.3f  largo %.3f' % (ext[0], ext[1], ext[2]))
    if ext[1] > min(ext[0], ext[2]):
        problemas.append('el alto (%.3f) no es la dimension menor: el modelo entra de pie'
                         % ext[1])
    print('PIVOTE       centro en (%.3f, %.3f, %.3f)' % tuple(centro))
    desvio = float(np.abs(centro).max() / mayor) if mayor else 0.0
    if desvio > PIVOTE_MAX:
        problemas.append('pivote desviado el %.1f%% del tamanio: al girar orbitara'
                         % (desvio * 100))

    # --- emision ---
    emite = False
    for mat in doc.get('materials', []):
        if 'emissiveTexture' in mat or any(v > 0.001 for v in mat.get('emissiveFactor', [0, 0, 0])):
            emite = True
    print('EMISION      %s' % ('declarada en el material' if emite else 'NO declarada'))
    if not emite:
        problemas.append('sin canal de emision: lo que brilla esta pintado en el albedo '
                         'y en el juego no va a brillar')

    # --- luz cocida ---
    base = None
    for mat in doc.get('materials', []):
        tex = mat.get('pbrMetallicRoughness', {}).get('baseColorTexture')
        if tex is not None:
            base = imgs.get(doc['textures'][tex['index']].get('source'))
            break
    if base is not None:
        d = desbalance_luz(base)
        print('LUZ COCIDA   desbalance del albedo %.3f  (aviso por encima de %.2f)' % (d, DESBALANCE))
        if d > DESBALANCE:
            avisos.append('el albedo se va %.0f%% de un lado a otro: abrelo y comprueba que no '
                          'trae iluminacion horneada' % (d * 100))
    else:
        avisos.append('sin textura de color base: no se pudo mirar la luz cocida')

    # --- lo que no rechaza pero conviene saber ---
    # El NOMBRE de la animacion no basta, y costo dos fallos averiguarlo. Uno: el
    # exportador de glTF tira la animacion entera sin dar error si el objeto tiene
    # dos modos de rotacion conviviendo, y el GLB sale con cero canales. Otro: si
    # cada pieza lleva su propia Action salen animaciones SEPARADAS —una por ala—
    # y el motor reproduce una sola, moviendo medio bicho. Las dos se ven aqui.
    anims = doc.get('animations', [])
    print('ANIMACIONES  %d' % len(anims))
    nombres_nodo = [n.get('name', '?') for n in doc.get('nodes', [])]
    for a in anims:
        print("             '%s'  %d canales" % (a.get('name', '(sin nombre)'), len(a['channels'])))
        for ch in a['channels']:
            s = a['samplers'][ch['sampler']]
            ti = doc['accessors'][s['input']]
            dur = ti.get('max', [0])[0]
            objetivo = nombres_nodo[ch['target']['node']] if 'node' in ch['target'] else '?'
            print('               %-20s %-11s %d claves  %.2fs'
                  % (objetivo[:20], ch['target']['path'], ti['count'], dur))
    if not anims:
        avisos.append('sin animaciones: el bicho va a estar quieto')
    elif len(anims) > 1:
        avisos.append('%d animaciones separadas: el motor reproduce una sola. Si cada pieza '
                      'lleva su propia Action, exporta con animation_mode=SCENE para que '
                      'salgan como una con varios canales' % len(anims))

    marcas = [n.get('name', '') for n in doc.get('nodes', [])
              if n.get('name', '').startswith(('tobera', 'canon'))]
    print('MARCADORES   %s' % (', '.join(marcas) if marcas else 'ninguno'))
    if not marcas:
        avisos.append('sin marcadores tobera_*/canon_*: no hay de donde colgar llamas ni disparos')

    if avisos_piezas:
        avisos.append(avisos_piezas)
    if len(nodos_malla) > 1 and len(doc.get('materials', [])) > 1:
        avisos.append('%d piezas con %d materiales: son varias draw calls por bicho. Lo ideal '
                      'es un material y un atlas para todo el modelo'
                      % (len(nodos_malla), len(doc['materials'])))

    return informe(problemas, avisos)


def informe(problemas, avisos):
    print('')
    for p in problemas:
        print('  RECHAZAR · %s' % p)
    for a in avisos:
        print('  AVISO    · %s' % a)
    if not problemas:
        print('  APTO · sin reparos que rechacen. Mirar igualmente el modelo con la luz '
              'de la escena antes de darlo por bueno.')
    return 1 if problemas else 0


if __name__ == '__main__':
    sys.exit(main())
