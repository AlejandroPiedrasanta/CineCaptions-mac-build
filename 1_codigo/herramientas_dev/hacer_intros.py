# CineCaptions · By Cinema Productions
# 1_codigo/herramientas_dev/hacer_intros.py — v5.33: los RECURSOS de las intros del «Gancho del inicio» (intros_gancho.py, estilos_pro 'gancho'):
#   * las LUCES base: los overlays de luz del usuario (pack «GANCHOS VIRALES», 5-OVERLAYS Y TRANSICIONES) recortados a su pico, en vertical y en
#     BLANCO Y NEGRO con dos mitades: a la izquierda la luz (luma) y a la derecha qué color le toca (0 = el primero, 1 = el segundo; sale del eje
#     de color principal de cada overlay). GO las colorea con los colores de la intro (o los del usuario): 2_recursos/efectos/intro/luz_<n>.mp4.
#   * los SONIDOS: una mezcla por intro (golpe + graves + textura) con el golpe en el instante 0: 2_recursos/efectos/sonidos/intro_<id>.wav.
#   * --previas: los ejemplos de las cartas (2_recursos/edicion_pro/estilos_pro/gancho_<id>.mp4 + .jpg) con el MISMO coloreado y zoom que GO.
#     python 1_codigo/herramientas_dev/hacer_intros.py [--luces] [--sonidos] [--previas] [--hoja]
import argparse
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import intros_gancho as IG  # noqa: E402

RAIZ = AQUI.parent.parent
OVERLAYS = Path(r'E:\VFX-EDICION VIDEOS\PREMIER PRO\GANCHOS VIRALES\ORIGINAL CINEMA\GANCHO VIRALES\GANCHO VIRALES\5-OVERLAYS Y TRANSICIONES')
PACK_SONIDOS = Path(r'E:\VFX-EDICION VIDEOS\PREMIER PRO\GANCHOS VIRALES\ORIGINAL CINEMA\GANCHO VIRALES\GANCHO VIRALES\6-SONIDOS')
SFX = RAIZ / '2_recursos' / 'sfx_library'

# luz: (archivo, fotograma de arranque en el overlay, velocidad, ganancia, girar 90°, isla a tapar (x0, x1, y1) en px del original o None)
FUENTES_LUZ = {
    'destello': ('CINEMA.mov', 0, 1.0, 1.0, False, (290, 740, 104)),        # blanco, violeta y verde con dos fogonazos
    'raya': ('CHRISS- Overlay 3.mp4', 8, 0.8, 3.2, False, None),            # una raya de luz que cruza por el lado
    'mancha': ('TR Flim Grain #1.mp4', 10, 0.8, 1.15, True, None),          # una mancha cálida que se abre
    'nube': ('TR Flim Grain #2.mp4', 5, 1.0, 1.1, True, None),              # luz que cambia de color y se va despacio
    'brasa': ('TR Flim Grain #5.mp4', 5, 0.75, 1.1, True, None),            # una mancha redonda que se apaga
}
LADO = (360, 640)                    # cada mitad (ancho, alto): las luces son difusas, GO las amplía sin que se note


def _decodificar(ruta):
    import av
    fr = []
    with av.open(str(ruta)) as c:
        s = c.streams.video[0]
        fps = float(s.average_rate or 30)
        for f in c.decode(s):
            fr.append(f.to_ndarray(format='rgb24'))
    return fr, fps


def _a_vertical(a, girar, isla):
    from PIL import Image
    a = a.astype(np.float32) / 255.0
    if isla:                                         # la «isla» negra de arriba (forma de móvil) del overlay: se rellena con la fila de debajo
        x0, x1, y1 = isla
        fila = a[y1 + 6:y1 + 7, x0:x1]
        a[:y1 + 6, x0:x1] = fila
        borde = 24                                   # costuras suaves a los lados
        for k in range(borde):
            w = (k + 1) / (borde + 1.0)
            for x in (x0 - borde + k, x1 + borde - 1 - k):
                a[:y1 + 6, x] = a[:y1 + 6, x] * w + fila[0, 0 if x < x0 else -1] * (1 - w)
    if girar:
        a = np.rot90(a)
    from PIL import ImageFilter
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).resize(LADO, Image.BILINEAR)
    # las motas y pelos oscuros de la película (anillos dentro de la luz): un «cierre» (máximo y luego mínimo) los tapa; la luz es difusa
    im = im.filter(ImageFilter.MaxFilter(23)).filter(ImageFilter.MinFilter(23)).filter(ImageFilter.GaussianBlur(2))
    a = np.asarray(im).astype(np.float32) / 255.0
    # y los anillos grandes: cada píxel, al menos el brillo difuminado de su alrededor (los huecos oscuros DENTRO de la luz se llenan)
    alrededor = np.asarray(im.filter(ImageFilter.GaussianBlur(22))).astype(np.float32) / 255.0
    return np.maximum(a, alrededor * 0.95)


def hacer_luces():
    import av
    destino = IG.carpeta() / 'intro'
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, (archivo, ini, vel, gan, girar, isla) in FUENTES_LUZ.items():
        fr, fps = _decodificar(OVERLAYS / archivo)
        verticales = [_a_vertical(a, girar, isla) for a in fr]
        # el eje de color principal del overlay (PCA de la crominancia de los píxeles con luz): separa sus dos colores
        muestras = np.concatenate([v.reshape(-1, 3)[::37] for v in verticales])
        y = muestras @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        muestras = muestras[y > 0.12]
        croma = muestras - muestras.mean(axis=1, keepdims=True)
        eje = np.linalg.svd(croma - croma.mean(axis=0), full_matrices=False)[2][0]
        n = int(round(IG.DUR_LUZ_S * IG.FPS_LUZ))
        lum = []
        tono = []
        for i in range(n):
            j = min(len(verticales) - 1, int(round(ini + i / IG.FPS_LUZ * fps * vel)))
            v = verticales[j]
            l = v @ np.array([0.2126, 0.7152, 0.0722], np.float32)
            c = v - v.mean(axis=2, keepdims=True)
            g = np.clip(0.5 + 2.2 * (c @ eje), 0.0, 1.0)
            lum.append(l)
            tono.append(g)
        lum = np.array(lum)
        lum = np.clip(lum * (0.92 * gan / max(1e-3, float(np.percentile(lum, 99.5)))), 0, 1)
        lum *= IG.cola(np.arange(n) / IG.FPS_LUZ)[:, None, None]          # se apaga del todo antes de 1 s
        ruta = destino / f'luz_{nombre}.mp4'
        with av.open(str(ruta), 'w') as out:
            s = out.add_stream('libx264', rate=IG.FPS_LUZ)
            s.width, s.height = LADO[0] * 2, LADO[1]
            s.pix_fmt = 'yuv420p'
            s.options = {'crf': '14', 'preset': 'slow', 'tune': 'grain'}
            for i in range(n):
                g8 = np.concatenate([lum[i], tono[i]], axis=1)
                rgb = np.repeat((g8 * 255 + 0.5).astype(np.uint8)[..., None], 3, axis=2)
                for p in s.encode(av.VideoFrame.from_ndarray(rgb, format='rgb24')):
                    out.mux(p)
            for p in s.encode():
                out.mux(p)
        print(f'luz {nombre}: {ruta.stat().st_size // 1024} KB')


# ----------------------------------------------------------------------------------------------------------------------- sonidos
SR = 48000


# v5.33 (el usuario: «los sonidos están muy básicos; arma y combina para crear algo que impacte»): cada intro es un DISEÑO de 5-7 capas con el
# golpe en el instante 0 — graves + sus armónicos (para que el golpe se oiga también en el altavoz del móvil) + cuerpo + chasquido + aire + un
# adorno de su tema — más el final de su «Viral Hooks Riser» AL REVÉS: arranca en el pico y se aleja, como el zoom. Cada capa se nivela igual
# (sus 200 ms más fuertes a -12 dBFS) antes de su ganancia, pasa por ffmpeg (inversión, tono, EQ, phaser, flanger, trémolo, bitcrush) y la mezcla
# por un máster común (pegado, sala corta, estéreo, saturación suave y limitador). Fuentes: los sonidos que el usuario pasó + su biblioteca
# EFECTOS SONIDO/UTILES (licencias: «yo respondo», 2026-10-13).
UTILES = Path(r'E:\VFX-EDICION VIDEOS\DAVINCI RESOLVE\EFECTOS SONIDO\UTILES')
PACK2 = Path(r'E:\VFX-EDICION VIDEOS\PREMIER PRO\GANCHOS VIRALES\GANCHO VIRALES\6-SONIDOS')
FUENTES_SONIDO = {           # nombre -> (archivo, segundo en el que ARRANCA su golpe: ahí cae el instante 0 de la intro)
    'riser': (PACK2 / 'Viral Hooks Riser.mp3', 2.825),                    # (su pico está al final: se usa al revés)
    'deep': (PACK2 / 'Deep Hit 3.wav', 0.0),
    'flash': (PACK2 / 'Vintage Flash.wav', 0.56),
    'booming': (UTILES / '1_Sfx - Varios' / 'RISERS Y TENSION' / 'Copia de Dauzkobza - Total Transitions - Booming Rise Deep Cinematic Outro.wav', 2.03),
    'camara1': (Path(r'E:\VFX-EDICION VIDEOS\DAVINCI RESOLVE\EFECTOS SONIDO\VARIADO\CAMARA\CAMARA (1).m4a'), 0.32),
    'intro_hit': (UTILES / 'Netflix Sounds' / 'THAT INTRO HIT.wav', 0.0),
    'subsonic': (UTILES / 'SFX RISEX' / 'Hits' / '07 Subsonic A.wav', 0.0),
    'boom': (UTILES / 'SFX RISEX' / 'Hits' / '01 Boom.wav', 0.0),
    'universe': (UTILES / 'SFX RISEX' / 'Hits' / '11 Universe Boom A.wav', 0.97),
    'struck': (UTILES / 'SFX RISEX' / 'Hits' / '09 Struck Down.wav', 0.25),
    'crash': (UTILES / 'SFX RISEX' / 'Hits' / '14 Incoming Crash.wav', 0.27),
    'shot': (UTILES / 'SFX RISEX' / 'Camera Flash' / 'camera shot flash 2.wav', 0.07),
    'glitch': (UTILES / 'SFX RISEX' / 'Glitches' / '18 Termainal Glitch.wav', 0.11),
    'glitch2': (UTILES / 'SFX RISEX' / 'Glitches' / '13 Restart Switch.wav', 0.16),
    'eglitch': (UTILES / 'SFX RISEX' / 'Other Sounds' / 'Electric Glitch 02.wav', 0.0),
    'ding': (UTILES / 'SFX RISEX' / 'Other Sounds' / 'Ding.mp3', 0.03),
    'thunder': (UTILES / 'Cinematic SFX' / 'IMPACTOS' / 'Copy of Thunder Hit.wav', 0.01),
    'air': (UTILES / 'Cinematic SFX' / 'IMPACTOS' / 'Copy of H2W Air Burst Dark 01.wav', 0.0),
    'slam': (UTILES / 'Cinematic SFX' / 'IMPACTOS' / 'Copy of Hit Impact Slam 01.wav', 0.0),
    'metal': (UTILES / 'Cinematic SFX' / 'IMPACTOS' / 'Copy of Hit Metal Reverb 07.wav', 0.0),
    'drum_rev': (UTILES / 'Cinematic SFX' / 'IMPACTOS' / 'Copy of Hit Drum Reverb 01.wav', 0.0),
    'fire': (UTILES / 'Cinematic SFX' / 'IMPACTOS' / 'Copy of H2W Fire Blast Processed 01.wav', 0.0),
    'deep_drum': (UTILES / '2_Sfx - Cinematic' / 'Bjorn Lynne -  Trailer Elements - Deep Drum Impact With Synth Chord.wav', 0.115),
    'ominous': (UTILES / '2_Sfx - Cinematic' / 'Chroma SFX - Ideal Impacts - Ominous Impact.wav', 0.48),
    'chispas': (UTILES / '2_Sfx - Cinematic' / 'Unrealsfx - Extreme Tension - Electricity Sparks Appearing Logo .wav', 0.0),
    'titanic': (UTILES / '2_Sfx - Cinematic' / 'Artlist Original - Cinematic Drums - Titanic Impact.wav', 4.10),
    'punch': (UTILES / 'Whooshes' / '14 Punch Whooshes' / '9_punch_whoosh_cinem8.wav', 0.0),
    'hitwhoosh': (UTILES / 'Whooshes' / '17 Hit Whooshes' / '5_hit_whoosh_cinem8.wav', 0.0),
    'bat': (UTILES / 'Artlist - 200+ Sound Effects' / 'Hits' / 'Gamemaster Audio - Close Combat - Hitting Baseball Bat Whack Wet Impact.wav', 0.0),
    'shimmer': (SFX / 'Idea' / 'Shimmer.wav', 0.0),
}
NIVEL_CAPA_DB = -12.0
# (el compresor deja pasar los primeros 15 ms: el golpe conserva su pico; luego pega las colas)
MASTER = ('highpass=f=28,acompressor=threshold=0.2:ratio=2.5:attack=15:release=180:makeup=1.5,aecho=0.8:0.6:45|90:0.16|0.1,extrastereo=m=1.25,'
          'asoftclip=type=atan:output=1,alimiter=limit=0.89:attack=1:release=60:level=0')


def _tono(k):
    """El tono (y la velocidad) por k: 0,8 = más grave y lento; 1,25 = más agudo y rápido."""
    return f'aresample={SR},asetrate={int(SR * k)},aresample={SR}'


def _ff(ruta, desde, largo, af=''):
    filtros = ','.join(x for x in (f'aresample={SR}', af) if x)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % max(0.0, desde), '-t', '%.3f' % largo, '-i', str(ruta), '-af', filtros,
                          '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).T.copy()


def _nivelar(a, db):
    v = max(1, int(0.2 * SR))
    m = a.mean(axis=0)
    n = len(m) // v
    fuerte = float(np.sqrt((m[:n * v].reshape(n, v) ** 2).mean(axis=1)).max()) if n else float(np.sqrt((m ** 2).mean()) + 1e-9)
    return a * (10 ** ((NIVEL_CAPA_DB + db - 20 * np.log10(max(fuerte, 1e-6))) / 20.0))


def C(nombre, db=0.0, en=0.0, af='', largo=2.4, antes=0.0, cae=None, sostiene=0.06):
    """Una capa: `nombre` de FUENTES_SONIDO desde su golpe (menos `antes` s), con `af` de ffmpeg, a `db` sobre el nivel común, en `en` s.
    `cae` = constante de tiempo (s) con la que se apaga tras `sostiene` s: los booms largos (de 2-8 s) suenan a golpe y no a muro."""
    ruta, ataque = FUENTES_SONIDO[nombre]
    a = _nivelar(_ff(ruta, ataque - antes, largo, af), db)
    if cae:
        t = np.arange(a.shape[1]) / SR
        a = a * np.exp(-np.maximum(0.0, t - sostiene) / cae)
    return int(en * SR), a


def R(largo, db=0.0, af=''):
    """El final del «Viral Hooks Riser» AL REVÉS: empieza en su pico y se aleja durante `largo` s (acompaña el zoom hacia fuera)."""
    ruta, pico = FUENTES_SONIDO['riser']
    a = _ff(ruta, pico - largo, largo, ','.join(x for x in ('areverse', af) if x))
    k = min(a.shape[1], int(0.012 * SR))
    a[:, :k] *= np.linspace(0.6, 1.0, k)                     # (el corte seco del pico, sin clic)
    return 0, _nivelar(a, db)


def _master(a):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ent = Path(d) / 'm.f32'
        ent.write_bytes(a.T.astype('<f4').tobytes())
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', str(ent), '-af', MASTER,
                              '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).T.copy()


def _mezcla(capas, largo):
    n = int(largo * SR)
    out = np.zeros((2, n), np.float32)
    for ini, a in capas:
        m = min(n - ini, a.shape[1])
        if m > 0:
            out[:, ini:ini + m] += a[:, :m]
    out = _master(out)[:, :n]
    f_in = int(0.002 * SR)
    out[:, :f_in] *= np.linspace(0, 1, f_in)
    t = np.arange(out.shape[1]) / SR
    u = np.clip((t - IG.SONIDO_FUNDE_S) / (largo - IG.SONIDO_FUNDE_S), 0, 1)
    out *= (0.5 + 0.5 * np.cos(np.pi * u))
    return out * ((10 ** (-1.0 / 20)) / max(float(np.abs(out).max()), 1e-6))


def _guardar_wav(a, ruta):
    pcm = (np.clip(a, -1, 1) * 32767).astype('<i2').T.copy()
    with wave.open(str(ruta), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


ARMONICOS = 'volume=14dB,asoftclip=type=tanh,highpass=f=90,lowpass=f=1400'     # los graves saturados: se oyen en un altavoz pequeño
REBOTES = (0.29, 0.58)                                                          # los rebotes del zoom «rebote» (intros_gancho.ZOOMS)


def mezclas():
    """Las 8 intros: capas pensadas para su luz y su zoom."""
    G, B = 0.35, 0.45                                     # cómo caen los graves y los booms (constante de tiempo, s)
    return {
        # golpe seco: fogonazo de cámara + boom + crack, y el barrido que se aleja
        'blanco': [C('flash', 0), C('shot', -4, af='highpass=f=900'), C('camara1', -6), C('deep', -1, cae=G), C('booming', -6, af='lowpass=f=900', cae=B),
                   C('intro_hit', -6, af=ARMONICOS, cae=0.25), C('slam', -2), R(0.45, -3, 'highpass=f=400')],
        # suave: una ráfaga de aire, graves redondos y un brillo; el barrido largo y sin agudos
        'lima': [C('air', -1), C('subsonic', -3, af='lowpass=f=180', cae=0.5), C('intro_hit', -8, af=ARMONICOS, cae=0.3), C('punch', -4),
                 C('shimmer', -12, en=0.04, cae=0.35), R(0.85, -1, 'lowpass=f=7000')],
        # desenfoque radial: chispazo eléctrico + golpe + whoosh de impacto; el barrido con flanger (zumbido de ciencia ficción)
        'neon': [C('chispas', -4, af='highpass=f=700', largo=1.3, cae=0.3), C('intro_hit', -1, af='lowpass=f=160', cae=G),
                 C('intro_hit', -6, af=ARMONICOS, cae=0.25), C('hitwhoosh', -2), C('shot', -7, af='highpass=f=1500'),
                 R(0.6, -3, 'flanger=delay=2:depth=6:speed=1.5')],
        # giro: impacto oscuro + boom de universo + metal más grave; el barrido con phaser (gira)
        'violeta': [C('ominous', -1, cae=B), C('universe', -5, af='lowpass=f=220', cae=B), C('metal', -5, af=_tono(0.85)), C('flash', -8),
                    C('intro_hit', -6, af=ARMONICOS, cae=0.25), R(0.65, -2, 'aphaser=type=t:speed=1.4:decay=0.6')],
        # temblor: estallido de fuego + trueno + boom; los graves con trémolo, como la sacudida
        'fuego': [C('fire', -1), C('thunder', -2, cae=B), C('boom', -5, af='lowpass=f=200', cae=G), C('crash', -8, af='highpass=f=500', cae=0.4),
                  C('intro_hit', -5, af=ARMONICOS + ',tremolo=f=16:d=0.6', cae=0.35), R(0.5, -5, 'tremolo=f=14:d=0.7')],
        # rebote: el boom de «Booming Rise» + la cámara + un tambor; y un golpe más agudo y más flojo en cada rebote del zoom
        'atardecer': [C('booming', 0, cae=B), C('camara1', -3), C('deep_drum', -3, cae=B), C('intro_hit', -7, af=ARMONICOS, cae=0.25),
                      C('deep', -8, en=REBOTES[0], af=_tono(1.25), cae=0.2), C('drum_rev', -10, en=REBOTES[0]),
                      C('deep', -14, en=REBOTES[1], af=_tono(1.5), cae=0.15), R(0.4, -6)],
        # RGB: glitch de terminal + reinicio + chispa eléctrica + golpe; el barrido «digital» (bitcrush)
        'hielo': [C('glitch', -1, cae=0.3), C('glitch2', -6, en=0.12, cae=0.25), C('eglitch', -3, af='highpass=f=1500', cae=0.25), C('subsonic', -4, af='lowpass=f=160', cae=G),
                  C('struck', -4, cae=B), C('intro_hit', -7, af=ARMONICOS, cae=0.25), R(0.5, -4, 'acrusher=bits=6:mode=log:aa=1')],
        # latigazo: whoosh de puñetazo más agudo + chasquido + tambor titánico; un brillo dulce encima
        'rosa': [C('punch', 0, af=_tono(1.15)), C('bat', -2), C('titanic', -3, af='lowpass=f=450', cae=B), C('deep', -5, cae=G),
                 C('intro_hit', -7, af=ARMONICOS, cae=0.25), C('shimmer', -11, cae=0.35), C('ding', -13, en=0.05, af=_tono(0.75)), R(0.35, -4)],
    }


def _bandas(a):
    """% de energía en graves (< 150 Hz), medios (150 Hz – 4 kHz) y agudos, en el primer medio segundo."""
    m = a.mean(axis=0)[:int(0.5 * SR)]
    sp = np.abs(np.fft.rfft(m)) ** 2
    fr = np.fft.rfftfreq(len(m), 1 / SR)
    tot = sp.sum() + 1e-12
    return [int(100 * sp[(fr >= lo) & (fr < hi)].sum() / tot) for lo, hi in ((0, 150), (150, 4000), (4000, SR))]


def hacer_sonidos(solo=None):
    destino = IG.carpeta() / 'sonidos'
    destino.mkdir(parents=True, exist_ok=True)
    for ident, capas in mezclas().items():
        if solo and ident not in solo:
            continue
        a = _mezcla(capas, IG.SONIDO_LARGO_S)
        ruta = destino / f'intro_{ident}.wav'
        _guardar_wav(a, ruta)
        m = a.mean(axis=0)
        v = int(0.1 * SR)
        rms = 20 * np.log10(np.sqrt((m[:len(m) // v * v].reshape(-1, v) ** 2).mean(axis=1)) + 1e-9)
        print(f'sonido {ident}: {len(capas)} capas · 100 ms: {" ".join(str(int(x)) for x in rms[:14])} dBFS · graves/medios/agudos {_bandas(a)} %')


# ----------------------------------------------------------------------------------------------------------------------- ejemplos de las cartas
VIDEO = Path.home() / 'Desktop' / 'VIDEOS EN ESPAÑOL' / 'PRUEBA ESPAÑOL.mp4'
W, H, FPS, DUR = 270, 480, 24, 3.2


def _fotogramas_video(desde=0.0):
    import av
    from PIL import Image
    out = []
    with av.open(str(VIDEO)) as c:
        s = c.streams.video[0]
        fps = float(s.average_rate or 30)
        for f in c.decode(s):
            t = float(f.time or 0)
            if t < desde:
                continue
            im = f.to_image()
            r = max(W / im.width, H / im.height)
            im = im.resize((int(im.width * r + 0.5), int(im.height * r + 0.5)), Image.BILINEAR)
            x0, y0 = (im.width - W) // 2, (im.height - H) // 2
            out.append(np.asarray(im.crop((x0, y0, x0 + W, y0 + H))).astype(np.float32) / 255.0)
            if t >= desde + DUR + 0.1:
                break
    idx = [min(len(out) - 1, int(round(i / FPS * fps))) for i in range(int(round(DUR * FPS)))]
    return [out[i] for i in idx]


def hacer_previas(solo=None, lateral=False):
    """Las cartas de Efectos (270×480, 3,2 s) o, con `lateral`, el ejemplo del menú lateral de Proyecto (ejemplos_pro/gancho.mp4, 432×936, 4 s,
    la intro automática)."""
    import av
    import estilos_pro as EST
    global W, H, DUR
    destino = RAIZ / '2_recursos' / 'edicion_pro' / 'estilos_pro'
    if lateral:
        W, H, DUR = 432, 936, 4.0
        destino = RAIZ / '2_recursos' / 'edicion_pro' / 'ejemplos_pro'
    base = _fotogramas_video()
    for v in [None] + ([] if lateral else [x for x in EST.seccion('gancho')['variantes']]):
        ident = v['id'] if v else ''
        if solo and (ident or 'auto') not in solo:
            continue
        intro = v or EST.variante('gancho', IG.POR_DEFECTO)        # (el ejemplo de «Automático» no depende del tema que tengas elegido)
        colores = EST.colores_de_variante('gancho', intro)
        luz = IG.colorear(intro, colores, W, H, FPS)
        cuadros = []
        for i, fr in enumerate(base):
            t = i / FPS
            a = IG.zoom_np(fr, intro['zoom'], t)
            if i < len(luz):
                a = 1.0 - (1.0 - a) * (1.0 - luz[i].astype(np.float32) / 255.0)       # modo Pantalla, como en Resolve
            cuadros.append((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))
        clave = 'gancho' if lateral else f'gancho_{ident or "auto"}'
        mp4 = destino / f'{clave}.mp4'
        wav = IG.carpeta() / 'sonidos' / f'intro_{intro["sonido"]}.wav'
        tmp = destino / f'{clave}_tmp.mp4'
        with av.open(str(tmp), 'w') as out:
            s = out.add_stream('libx264', rate=FPS)
            s.width, s.height, s.pix_fmt = W, H, 'yuv420p'
            s.options = {'crf': '26', 'preset': 'slow'}
            for c in cuadros:
                for p in s.encode(av.VideoFrame.from_ndarray(c, format='rgb24')):
                    out.mux(p)
            for p in s.encode():
                out.mux(p)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(tmp), '-i', str(wav), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '96k',
                        '-af', 'apad', '-shortest', '-movflags', '+faststart', str(mp4)], check=True)
        tmp.unlink()
        from PIL import Image
        # el póster: entre 0,06 y 0,45 s, el fotograma con la luz bien visible pero sin quemar (en el fogonazo la carta salía en blanco)
        tramo = range(int(0.06 * FPS), int(0.45 * FPS))
        mejor = min(tramo, key=lambda i: abs(float(cuadros[i].mean()) - 175.0))
        Image.fromarray(cuadros[mejor]).save(destino / f'{clave}.jpg', quality=86)
        print(f'ejemplo {clave}: {mp4.stat().st_size // 1024} KB')


def hoja(ruta):
    """Una hoja para revisar: cada intro en una fila, 9 fotogramas de 0 a 1 s."""
    from PIL import Image
    import estilos_pro as EST
    filas = []
    base = _fotogramas_video()
    for v in EST.seccion('gancho')['variantes']:
        luz = IG.colorear(v, EST.colores_de_variante('gancho', v), W, H, FPS)
        fila = []
        for i in (0, 1, 2, 3, 4, 6, 8, 12, 18):
            a = IG.zoom_np(base[i], v['zoom'], i / FPS)
            a = 1.0 - (1.0 - a) * (1.0 - luz[i].astype(np.float32) / 255.0) if i < len(luz) else a
            fila.append((np.clip(a, 0, 1) * 255).astype(np.uint8)[::2, ::2])
        filas.append(np.concatenate(fila, axis=1))
    Image.fromarray(np.concatenate(filas, axis=0)).save(ruta, quality=88)
    print('hoja:', ruta)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--luces', action='store_true')
    ap.add_argument('--sonidos', action='store_true')
    ap.add_argument('--previas', action='store_true')
    ap.add_argument('--lateral', action='store_true', help='el ejemplo del menú lateral de Proyecto (ejemplos_pro/gancho.mp4)')
    ap.add_argument('--solo', default='', help='ejemplos: ids separados por comas (auto = Automático)')
    ap.add_argument('--hoja', default='', help='ruta .jpg de una hoja de revisión')
    a = ap.parse_args()
    if a.luces:
        hacer_luces()
    if a.sonidos:
        hacer_sonidos(set(x for x in a.solo.split(',') if x) or None)
    if a.previas:
        hacer_previas(set(x for x in a.solo.split(',') if x) or None)
    if a.lateral:
        hacer_previas(lateral=True)
    if a.hoja:
        hoja(a.hoja)
