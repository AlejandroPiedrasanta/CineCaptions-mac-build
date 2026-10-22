# CineCaptions · By Cinema Productions
# 1_codigo/intros_gancho.py — v5.33: el «Gancho del inicio» de la Edición PRO = una INTRO en el primer segundo: un destello de luz (los overlays
# del usuario, coloreados), el video que hace zoom hacia FUERA y un golpe de sonido mezclado.
"""
intros_gancho.py  (v5.33)
-------------------------
El usuario (2026-10-20, con 3 reels de referencia y su pack «GANCHOS VIRALES»): «va a ser intros de overlays con zoom para fuera y su sonido;
la intro tiene que ser en el primer segundo 0-1 s; solo deja 8 opciones, que cambie de color y música y tipo de zoom; haz que la intro sea
impactante y acompáñalo con sonido; si es necesario mezcla varios». En las referencias, el fotograma 0 es un fogonazo de color a pantalla completa
que se apaga en ~0,3 s mientras el video se aleja.

Las 8 intros son los estilos de la sección 'gancho' de estilos_pro (fuente única del catálogo): cada una trae su luz (`luz`), sus dos colores
(paleta o `a`), su zoom (`zoom`) y su sonido (`sonido`). Los colores de la fila «Colores» de Efectos (acento / acento2) mandan sobre los suyos.

    activa(op)                  -> ¿va la intro en este GO? (Edición PRO en juego + interruptor «Gancho del inicio»)
    elegida(op) -> (intro, colores)   la intro del usuario (o la automática por tema) y sus colores finales
    eventos(op, video)          -> los eventos del plan de efectos (efectos_visuales): la luz, el sonido y el zoom de V1
    colorear(intro, colores, ancho, alto, fps) -> [RGB uint8]  la luz coloreada (se mezcla en Pantalla); también para los ejemplos
    preparar_clip(...)          -> mp4 de la luz para Resolve (en ~/DaVinciSubtitles/efectos_clips/gancho: Resolve lo deja abierto)
    preparar_sonido(intro, video) -> (wav, s) el sonido nivelado bajo la voz de ESE video
    expresiones(tipo, fps)      -> el zoom en expresiones de Fusion (fusion_v1 lo mete en la comp de V1)
    zoom_np(cuadro, tipo, t)    -> el MISMO zoom en numpy (los ejemplos de las cartas, herramientas_dev/hacer_intros.py)
    fin_zoom_s(op)              -> cuándo termina el zoom (la PRO no recorta a la persona antes: el recorte no casaría)

Recursos (herramientas_dev/hacer_intros.py): 2_recursos/efectos/intro/luz_<n>.mp4 (luz | qué color, en gris) y efectos/sonidos/intro_<id>.wav.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

DUR_LUZ_S = 1.0                      # todo pasa en el primer segundo
FPS_LUZ = 30
SONIDO_LARGO_S = 2.2                 # el golpe suena en 0 y su cola (boom y sala) se funde desde SONIDO_FUNDE_S
SONIDO_FUNDE_S = 1.2
NOMBRE_COMP = 'CineCaptions Intro'   # (≠ «CineCaptions FX»: colocar_pro no recorta a la persona sobre un clip con el movimiento de Efectos)
REVISION = 'i2'                      # súbela si cambia el coloreado: se rehacen los clips
SOBRE_LA_VOZ_DB = -3.0               # lo más fuerte del golpe (100 ms), respecto a lo más fuerte de la voz (los efectos normales van 9 dB por
                                     # debajo; en las referencias, el golpe de la intro queda 2-3 dB bajo los picos de la voz)
LADO_INTERNO = 960                   # la luz se colorea a este lado mayor como mucho y se amplía (es difusa: no se nota y va 4 veces más rápido)
CLIPS = Path.home() / 'DaVinciSubtitles' / 'efectos_clips' / 'gancho'

# el zoom hacia fuera: d = cuánto dura (s), a = cuánto más cerca empieza, p = la curva (más alto = suelta más de golpe)
ZOOMS = {
    'golpe': {'d': 0.42, 'a': 0.30, 'p': 4},
    'suave': {'d': 0.90, 'a': 0.16, 'p': 3},
    'desenfoque': {'d': 0.55, 'a': 0.26, 'p': 3, 'zblur': 0.30},
    'giro': {'d': 0.65, 'a': 0.30, 'p': 3, 'giro': 8.0},
    'temblor': {'d': 0.60, 'a': 0.22, 'p': 3, 'temblor': 0.018},
    'rebote': {'d': 0.75, 'a': 0.26, 'p': 2, 'rebote': 2.6},
    'rgb': {'d': 0.50, 'a': 0.20, 'p': 3, 'rgb': 0.022},
    'latigo': {'d': 0.45, 'a': 0.20, 'p': 3, 'latigo': 0.30, 'dblur': 0.25},
}
NOMBRES_ZOOM = {'golpe': 'Golpe seco', 'suave': 'Suave', 'desenfoque': 'Desenfocado', 'giro': 'Con giro', 'temblor': 'Con temblor',
                'rebote': 'Con rebote', 'rgb': 'RGB', 'latigo': 'Latigazo'}
SIN_ZOOM = 'ninguno'
# «Automático»: la intro que va con cada tema (el pack de go_pack)
POR_TEMA = {'Kinetic': 'rosa', 'Referencia': 'blanco', 'VIRAL': 'neon', 'Tema4': 'hielo', 'Tema5': 'violeta', 'Tema6': 'atardecer'}
POR_DEFECTO = 'blanco'


def carpeta():
    try:
        from sfx_rules import base_recursos
        return Path(base_recursos()) / 'efectos'
    except Exception:
        return Path(__file__).resolve().parent.parent / '2_recursos' / 'efectos'


# ----------------------------------------------------------------------------------------------------------------------- qué intro
def _op(op):
    if op is not None:
        return op
    try:
        import edicion_pro
        return edicion_pro.opciones_guardadas()
    except Exception:
        return {}


def activa(op=None):
    """¿Va la intro en el próximo GO? Con la Edición PRO en juego y el «Gancho del inicio» encendido (menú lateral de Proyecto / Efectos)."""
    try:
        import edicion_pro
        import pro_lateral_ui as LAT
        return bool(edicion_pro.en_juego()) and bool(LAT.estado('gancho', _op(op)))
    except Exception:
        return False


def automatica(op=None):
    """La intro de «Automático»: la del tema elegido."""
    import estilos_pro as EST
    try:
        import edicion_pro
        tema = edicion_pro.tema_actual()
    except Exception:
        tema = ''
    return EST.variante('gancho', POR_TEMA.get(tema, POR_DEFECTO)) or EST.seccion('gancho')['variantes'][0]


def elegida(op=None):
    """(intro, colores {'acento', 'acento2'}): la del usuario (o la automática) con sus colores; los de la fila «Colores» mandan."""
    import estilos_pro as EST
    v, c = EST.resolver('gancho', _op(op))
    intro = v or automatica(op)
    colores = EST.colores_de_variante('gancho', intro)
    colores.update(c)                                # (con Automático, `c` son solo los del usuario)
    return intro, colores


def eleccion_zoom(op=None):
    """v5.33 (el usuario: «te faltó el botón de efecto de zoom»): '' = el de la intro, un tipo de ZOOMS o SIN_ZOOM (pro_estilos['gancho']['z'])."""
    import estilos_pro as EST
    return (EST.leer(_op(op)).get('gancho') or {}).get('z', '')


def zoom_de(intro, eleccion=''):
    """El tipo de zoom que hace GO con `intro` y esa elección (None = sin zoom)."""
    if eleccion == SIN_ZOOM:
        return None
    return eleccion if eleccion in ZOOMS else (intro.get('zoom') if intro.get('zoom') in ZOOMS else 'golpe')


def nombre_zoom(eleccion, intro=None):
    if not eleccion:
        return NOMBRES_ZOOM.get((intro or {}).get('zoom'), 'El de la intro') if intro else 'El de la intro'
    return 'Sin zoom' if eleccion == SIN_ZOOM else NOMBRES_ZOOM.get(eleccion, eleccion)


def fin_zoom_s(op=None):
    """Cuándo termina el zoom de la intro (0 = sin zoom)."""
    intro, _c = elegida(op)
    z = zoom_de(intro, eleccion_zoom(op))
    return float(ZOOMS[z]['d']) if z else 0.0


def eventos(op=None, video=None):
    """Los eventos del plan de efectos: la luz (FX-INTRO, en Pantalla), el sonido (FX-SONIDO; el de la fila «Sonido») y, en `v1`, el zoom."""
    intro, colores = elegida(op)
    evs = [{'tipo': 'intro', 'ini': 0.0, 'asset': f"gancho_{intro['id']}", 'gancho': {'id': intro['id'], 'colores': colores}}]
    eleccion = eleccion_sonido(op)
    try:
        wav, dur = preparar_sonido(intro, video, eleccion)
    except Exception:
        wav, dur = None, 0.0
    if wav:
        evs.append({'tipo': 'sonido', 'ini': 0.0, 'archivo': wav, 'dur': round(dur, 3), 'asset': f"Intro {nombre_sonido(eleccion, intro)}"})
    return evs, intro


# ----------------------------------------------------------------------------------------------------------------------- la luz
_LUCES = {}


def _luz(nombre):
    """Los fotogramas de una luz base: [(luz, qué color)] en float32 0..1 (360×640, vertical) a FPS_LUZ."""
    if nombre in _LUCES:
        return _LUCES[nombre]
    import av
    import numpy as np
    ruta = carpeta() / 'intro' / f'luz_{nombre}.mp4'
    out = []
    with av.open(str(ruta)) as c:
        for f in c.decode(video=0):
            g = f.to_ndarray(format='gray').astype(np.float32) / 255.0
            m = g.shape[1] // 2
            out.append((g[:, :m], g[:, m:]))
    _LUCES[nombre] = out
    return out


def cola(t):
    """El final de la luz: entera hasta 0,3 s y fundida a negro a los 0,75 s (las referencias ya enseñan el video limpio a ~0,3 s)."""
    import numpy as np
    t = np.asarray(t, dtype=np.float32)
    u = np.clip((t - 0.3) / 0.45, 0.0, 1.0)
    return 0.5 + 0.5 * np.cos(np.pi * u)


def _rgb(h):
    h = str(h or '#FFFFFF').lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _vivo(c):
    """El color a toda luz (el canal más alto a 1): una luz no es «oscura», es menos intensa."""
    m = max(c) or 1.0
    return tuple(x / m for x in c)


def colorear(intro, colores, ancho, alto, fps):
    """La luz de la intro, coloreada, del tamaño del timeline y a sus fps: [RGB uint8 (alto, ancho, 3)] durante DUR_LUZ_S.
    luz → negro / color / un poco de blanco en los núcleos (`blanco`) + el fogonazo del color en el fotograma 0, como en las referencias."""
    import numpy as np
    from PIL import Image
    base = _luz(intro.get('luz') or 'destello')
    c1 = np.array(_vivo(_rgb(colores.get('acento') or '#FFFFFF')), np.float32)
    c2 = np.array(_vivo(_rgb(colores.get('acento2') or colores.get('acento') or '#FFFFFF')), np.float32)
    blanco = float(intro.get('blanco', 0.35))
    fog = (c1 + c2) / 2.0
    fog = fog + (1.0 - fog) * blanco * 0.5
    pico, tau = float(intro.get('fogonazo', 0.9)), float(intro.get('tau', 0.06))
    girar = ancho > alto * 1.05                     # en horizontal, la luz (hecha en vertical) se gira
    final = (ancho, alto)
    k = min(1.0, LADO_INTERNO / float(max(ancho, alto)))
    ancho, alto = max(2, int(round(ancho * k))), max(2, int(round(alto * k)))
    n = int(math.ceil(DUR_LUZ_S * float(fps)))
    out = []
    for i in range(n):
        t = i / float(fps)
        j = min(len(base) - 1, int(round(t * FPS_LUZ)))
        lum, ton = base[j]
        if girar:
            lum, ton = np.rot90(lum), np.rot90(ton)
        h0, w0 = lum.shape
        r = max(ancho / w0, alto / h0)              # llena el cuadro (lo que sobra se recorta al centro)
        tw, th = int(math.ceil(w0 * r)), int(math.ceil(h0 * r))
        x0, y0 = (tw - ancho) // 2, (th - alto) // 2
        L = np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).resize((tw, th), Image.BILINEAR))[y0:y0 + alto, x0:x0 + ancho]
        G = np.asarray(Image.fromarray((ton * 255).astype(np.uint8)).resize((tw, th), Image.BILINEAR))[y0:y0 + alto, x0:x0 + ancho]
        L = np.clip((L.astype(np.float32) / 255.0 - 0.03) / 0.97, 0.0, 1.0)[..., None]
        G = (G.astype(np.float32) / 255.0)[..., None]
        c = c1 * (1.0 - G) + c2 * G
        rgb = c * (np.minimum(L, 0.8) / 0.8) ** 1.3 + (1.0 - c) * blanco * (np.clip(L - 0.8, 0.0, 0.2) / 0.2) ** 2
        F = pico * math.exp(-t / tau)
        if F > 0.004:
            rgb = 1.0 - (1.0 - rgb) * (1.0 - F * fog)
        c8 = (np.clip(rgb, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
        if (ancho, alto) != final:
            c8 = np.asarray(Image.fromarray(c8).resize(final, Image.BILINEAR))
        out.append(c8)
    return out


def preparar_clip(intro, colores, ancho, alto, fps):
    """El mp4 de la luz (negro = nada en Pantalla) para el timeline: ancho×alto a sus fps. Se reusa si ya está hecho."""
    import av
    from fractions import Fraction
    base = carpeta() / 'intro' / f"luz_{intro.get('luz') or 'destello'}.mp4"
    try:
        sello = base.stat().st_mtime_ns
    except OSError:
        return None
    clave = hashlib.md5(f"{intro['id']}|{sorted((colores or {}).items())}|{ancho}x{alto}|{float(fps):.3f}|{sello}|{REVISION}".encode('utf-8')).hexdigest()[:12]
    ruta = CLIPS / f"intro_{intro['id']}_{clave}.mp4"
    if ruta.is_file() and ruta.stat().st_size > 2000:
        return ruta
    CLIPS.mkdir(parents=True, exist_ok=True)
    cuadros = colorear(intro, colores, int(ancho) // 2 * 2, int(alto) // 2 * 2, fps)
    tmp = ruta.with_suffix('.tmp.mp4')
    with av.open(str(tmp), 'w') as out:
        s = out.add_stream('libx264', rate=Fraction(float(fps)).limit_denominator(1001))
        s.width, s.height, s.pix_fmt = int(ancho) // 2 * 2, int(alto) // 2 * 2, 'yuv420p'
        s.options = {'crf': '16', 'preset': 'fast'}
        for c in cuadros:
            for p in s.encode(av.VideoFrame.from_ndarray(c, format='rgb24')):
                out.mux(p)
        for p in s.encode():
            out.mux(p)
    tmp.replace(ruta)
    return ruta


# ----------------------------------------------------------------------------------------------------------------------- el sonido
SIN_SONIDO = 'ninguno'


def ruta_sonido(intro):
    return carpeta() / 'sonidos' / f"intro_{intro.get('sonido') or intro['id']}.wav"


def eleccion_sonido(op=None):
    """v5.33, la fila «Sonido» de Efectos (el usuario: «por si el sonido por defecto no me gusta»): '' = el de la intro, el id de otra intro,
    SIN_SONIDO o la ruta de un archivo del usuario (estilos_pro: pro_estilos['gancho']['s'])."""
    import estilos_pro as EST
    return (EST.leer(_op(op)).get('gancho') or {}).get('s', '')


def fuente_sonido(intro, eleccion=''):
    """El archivo de sonido que va con `intro` según la elección (None = sin sonido)."""
    import estilos_pro as EST
    if eleccion == SIN_SONIDO:
        return None
    if eleccion:
        otra = EST.variante('gancho', eleccion)
        if otra is not None:
            return ruta_sonido(otra)
        if Path(eleccion).is_file():
            return Path(eleccion)
    return ruta_sonido(intro)


def nombre_sonido(eleccion, intro=None):
    import estilos_pro as EST
    if not eleccion:
        return intro['nombre'] if intro else 'El de la intro'
    if eleccion == SIN_SONIDO:
        return 'Sin sonido'
    v = EST.variante('gancho', eleccion)
    return v['nombre'] if v else Path(eleccion).stem


def _alinear_propio(ruta, rate):
    """Un sonido del usuario hecho intro: empieza 20 ms antes de su golpe (la primera ventana de 10 ms a menos de 12 dB de lo más fuerte de sus 3
    primeros segundos), dura SONIDO_LARGO_S, se funde desde SONIDO_FUNDE_S y queda a -1 dBFS. → (muestras, 2) float32 o None."""
    import numpy as np
    import efectos_visuales
    a = efectos_visuales._decodificar_audio(ruta, rate)
    if a.shape[1] == 0 or float(np.abs(a).max()) <= 1e-6:
        return None
    paso = int(0.01 * rate)
    m = a.mean(axis=0)[:3 * rate]
    nv = max(1, len(m) // paso)
    db = 20.0 * np.log10(np.sqrt((m[:nv * paso].reshape(nv, paso) ** 2).mean(axis=1)) + 1e-9) if len(m) >= paso else np.zeros(1)
    k = int(np.argmax(db >= db.max() - 12.0))
    ini = max(0, (k - 2) * paso)
    n = int(SONIDO_LARGO_S * rate)
    t = a[:, ini:ini + n]
    if t.shape[1] < n:
        t = np.pad(t, ((0, 0), (0, n - t.shape[1])))
    t = t.copy()
    f = int(0.002 * rate)
    t[:, :f] *= np.linspace(0.0, 1.0, f, dtype=np.float32)
    u = np.clip((np.arange(n) / float(rate) - SONIDO_FUNDE_S) / (SONIDO_LARGO_S - SONIDO_FUNDE_S), 0.0, 1.0)
    t *= (0.5 + 0.5 * np.cos(np.pi * u)).astype(np.float32)
    t *= (10.0 ** (-1.0 / 20.0)) / max(float(np.abs(t).max()), 1e-6)
    return t.T


def preparar_sonido(intro, video=None, eleccion=''):
    """(wav, duración_s): el sonido de la intro (o el elegido en la fila «Sonido») con lo más fuerte del golpe (100 ms) SOBRE_LA_VOZ_DB respecto a
    la voz de ESE video (pico ≤ -1 dBFS); (None, 0) = sin sonido. Sin voz medida, tal cual (ya viene a -1 dBFS de pico). En la carpeta del
    usuario: Resolve lo deja abierto."""
    import wave
    import numpy as np
    origen = fuente_sonido(intro, eleccion)
    if origen is None or not Path(origen).is_file():
        return None, 0.0
    origen = Path(origen)
    propio = origen.parent.resolve() != (carpeta() / 'sonidos').resolve()
    voz = None
    if video:
        try:
            import sfx_rules
            voz = sfx_rules.fijar_voz(video)
        except Exception:
            voz = None
    clave = hashlib.md5(f'{origen.resolve()}|{origen.stat().st_mtime_ns}|{voz}|{SOBRE_LA_VOZ_DB}|{SONIDO_LARGO_S}'.encode('utf-8')).hexdigest()[:10]
    destino = CLIPS / f"sonido_{intro['id']}_{clave}.wav"
    if destino.is_file() and destino.stat().st_size > 1000:
        with wave.open(str(destino), 'rb') as w:
            return str(destino), w.getnframes() / float(w.getframerate())
    if propio:
        rate, canales = 48000, 2
        a = _alinear_propio(origen, rate)
        if a is None:
            return None, 0.0
    else:
        with wave.open(str(origen), 'rb') as w:
            rate, canales, n = w.getframerate(), w.getnchannels(), w.getnframes()
            datos = w.readframes(n)
        a = np.frombuffer(datos, '<i2').astype(np.float32).reshape(-1, canales) / 32767.0
    n = a.shape[0]
    if voz is not None:
        m = a.mean(axis=1)
        v = max(1, int(rate * 0.1))
        nv = len(m) // v
        fuerte = float(np.sqrt((m[:nv * v].reshape(nv, v) ** 2).mean(axis=1)).max()) if nv else float(np.sqrt((m ** 2).mean()))
        g = 10.0 ** ((float(voz) + SOBRE_LA_VOZ_DB - 20.0 * math.log10(max(fuerte, 1e-6))) / 20.0)
        a = a * min(g, (10.0 ** (-1.0 / 20.0)) / max(float(np.abs(a).max()), 1e-6))
    CLIPS.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), 'wb') as w:
        w.setnchannels(canales)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(a, -1.0, 1.0) * 32767.0).astype('<i2').tobytes())
    return str(destino), n / float(rate)


# ----------------------------------------------------------------------------------------------------------------------- el zoom
def _curva(tipo, t):
    """(escala, giro°, dx, dy, desenfoque_zoom, desenfoque_vertical, separación_rgb) en el instante t (s). dx/dy en fracción del cuadro
    (dy > 0 = la imagen más ABAJO)."""
    z = ZOOMS.get(tipo) or ZOOMS['golpe']
    u = min(1.0, max(0.0, t / z['d']))
    r = 1.0 - u
    if 'rebote' in z:
        s = 1.0 + z['a'] * r ** 2 * abs(math.cos(z['rebote'] * math.pi * u))
    else:
        s = 1.0 + z['a'] * r ** z['p']
    ang = z.get('giro', 0.0) * r ** 3
    dx = z.get('temblor', 0.0) * r ** 2 * math.sin(t * 71.0)
    dy = 0.8 * z.get('temblor', 0.0) * r ** 2 * math.sin(t * 53.0 + 1.7) + z.get('latigo', 0.0) * r ** 4
    return s, ang, dx, dy, z.get('zblur', 0.0) * r ** 2, z.get('dblur', 0.0) * r ** 3, z.get('rgb', 0.0) * r ** 2


def expresiones(tipo, fps, desde=0):
    """El zoom en expresiones de Fusion (Lua, `time` = fotograma de la comp; `desde` = el fotograma de la comp donde empieza la intro):
    {'size', 'dx', 'dy', 'angulo', 'zblur', 'dblur', 'rgb'} (None = no lleva). dy en coordenadas de Fusion (y hacia ARRIBA)."""
    z = ZOOMS.get(tipo) or ZOOMS['golpe']
    fps = float(fps or 30)
    df = '%.3f' % (z['d'] * fps)
    tt = '(time-%d)' % int(desde)
    u = 'math.min(1,math.max(0,%s/%s))' % (tt, df)
    r = '(1-%s)' % u
    seg = '(%s/%.4f)' % (tt, fps)
    if 'rebote' in z:
        size = '(1+%.4f*%s^2*math.abs(math.cos(%.4f*math.pi*%s)))' % (z['a'], r, z['rebote'], u)
    else:
        size = '(1+%.4f*%s^%d)' % (z['a'], r, z['p'])
    e = {'size': size, 'dx': None, 'dy': None, 'angulo': None, 'zblur': None, 'dblur': None, 'rgb': None}
    if z.get('temblor'):
        e['dx'] = '%.4f*%s^2*math.sin(%s*71)' % (z['temblor'], r, seg)
        e['dy'] = '%.4f*%s^2*math.sin(%s*53+1.7)' % (-0.8 * z['temblor'], r, seg)
    if z.get('latigo'):
        e['dy'] = '%.4f*%s^4' % (-z['latigo'], r)
    if z.get('giro'):
        e['angulo'] = '%.4f*%s^3' % (z['giro'], r)
    if z.get('zblur'):
        e['zblur'] = '%.4f*%s^2' % (z['zblur'], r)
    if z.get('dblur'):
        e['dblur'] = '%.4f*%s^3' % (z['dblur'], r)
    if z.get('rgb'):
        e['rgb'] = '%.4f*%s^2' % (z['rgb'], r)
    return e


def zoom_np(cuadro, tipo, t):
    """El mismo zoom que la comp de Fusion, sobre un fotograma RGB float 0..1 (para los ejemplos). Bordes en espejo, como Edges = Mirror."""
    import numpy as np
    from PIL import Image
    s, ang, dx, dy, zb, db, sep = _curva(tipo, t)
    if s <= 1.0001 and abs(ang) < 1e-3 and abs(dx) < 1e-5 and abs(dy) < 1e-5 and zb < 1e-4 and db < 1e-4 and sep < 1e-5:
        return cuadro
    h, w = cuadro.shape[:2]
    pad = max(h, w) // 2
    grande = np.pad(cuadro, ((pad, pad), (pad, pad), (0, 0)), mode='reflect')
    im = Image.fromarray((np.clip(grande, 0, 1) * 255).astype(np.uint8))

    def uno(escala, ddy=0.0):
        a = math.radians(-ang)                       # (Fusion gira en sentido antihorario con el ángulo positivo; aquí y va hacia abajo)
        ca, sa = math.cos(a) / escala, math.sin(a) / escala
        cx, cy = pad + w / 2.0 - dx * w, pad + h / 2.0 - (dy + ddy) * h
        # de cada píxel de salida (x, y) al de entrada: centro + R(-ang)/escala · (x - w/2, y - h/2)
        datos = (ca, sa, cx - ca * w / 2.0 - sa * h / 2.0, -sa, ca, cy + sa * w / 2.0 - ca * h / 2.0)
        return np.asarray(im.transform((w, h), Image.AFFINE, datos, resample=Image.BILINEAR)).astype(np.float32) / 255.0

    if zb > 1e-3:
        capas = [uno(s * (1.0 + zb * k / 5.0)) for k in range(6)]
    elif db > 1e-3:
        capas = [uno(s, db * (k / 5.0 - 0.5)) for k in range(6)]
    else:
        capas = [uno(s)]
    a = sum(capas) / len(capas)
    if sep > 1e-4:
        k = int(round(sep * w))
        if k:
            a = a.copy()
            a[..., 0] = np.roll(a[..., 0], -k, axis=1)
            a[..., 2] = np.roll(a[..., 2], k, axis=1)
    return a


# ----------------------------------------------------------------------------------------------------------------------- oír (Efectos)
def oir(ident, reproductor, eleccion=None):
    """Suena lo que GO pondría con la intro `ident` ('' = la automática) y el sonido `eleccion` (None = el guardado en la fila «Sonido») en
    `reproductor` (sfx_audio.Reproductor). Lee y prepara el archivo: llamar desde un hilo. Sin sonido: no suena nada."""
    import estilos_pro as EST
    import sfx_audio
    intro = EST.variante('gancho', ident) if ident else automatica()
    if intro is None:
        return False
    wav, _d = preparar_sonido(intro, None, eleccion_sonido() if eleccion is None else eleccion)
    if not wav:
        reproductor.detener()
        return False
    audio, _ = sfx_audio.cargar(wav)
    if len(audio):
        reproductor.reproducir(audio)
        return True
    return False
